#!/usr/bin/env python3
"""Realtime live camera: local window + MJPEG web stream.

Both outputs show the sign detector overlay and the LED state.

Examples:
    # Window on HDMI + stream at http://<jetson-ip>:8000/
    python3 tools/live_camera.py

    # Headless (SSH): web stream only, simulated GPIO
    python3 tools/live_camera.py --no-window --simulate-gpio

    # USB camera
    python3 tools/live_camera.py --camera usb --usb-index 0
"""

import argparse
import datetime
import os
import signal
import socket
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import cv2

from signrec.camera import CameraError, open_camera
from signrec.config import load_config
from signrec.decision import DecisionLogic
from signrec.detector import SignDetector
from signrec.gpio_led import LedController
from signrec.overlay import render_overlay
from signrec.webstream import LiveStreamServer

STOP_REQUESTED = {"value": False}
WINDOW_NAME = "Jetson Live Camera"


def _handle_signal(signum, frame):
    STOP_REQUESTED["value"] = True


def _local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def _status_line(result, detection, fps, threshold, elapsed):
    if result.sign is not None:
        headline = "SIGN=%-5s conf=%.2f" % (result.sign, result.confidence)
    elif detection is not None:
        headline = "cand=%-5s conf=%.2f < %.2f" % (
            detection.label, detection.confidence, threshold)
    else:
        headline = "SIGN=--    no detection"
    return "[%s] %s | SAFE=%-3s | %.1f FPS | %.1fs" % (
        datetime.datetime.now().strftime("%H:%M:%S"), headline,
        "yes" if result.safe else "no", fps, elapsed)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Realtime live camera with sign overlay and web stream",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--config", default=None)
    parser.add_argument("--camera", choices=("csi", "usb"), default=None)
    parser.add_argument("--sensor-id", type=int, default=None)
    parser.add_argument("--usb-index", type=int, default=None)
    parser.add_argument("--flip", choices=("none", "horizontal", "vertical",
                                           "rotate180"), default=None)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--no-window", action="store_true",
                        help="Disable the local OpenCV window")
    parser.add_argument("--no-stream", action="store_true",
                        help="Disable the MJPEG web stream")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Web server bind address")
    parser.add_argument("--port", type=int, default=8000,
                        help="Web server port")
    parser.add_argument("--quality", type=int, default=80,
                        help="JPEG quality for the stream (1-100)")
    parser.add_argument("--stream-width", type=int, default=960,
                        help="Downscale stream frames wider than this "
                             "(0 = keep original)")
    parser.add_argument("--simulate-gpio", action="store_true",
                        help="Do not touch real GPIO pins")
    parser.add_argument("--duration", type=float, default=0.0,
                        help="Stop after N seconds (0 = unlimited)")
    parser.add_argument("--status-interval", type=float, default=1.0,
                        help="Seconds between terminal status lines")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)

    threshold = args.threshold
    if threshold is None:
        threshold = config["detector"].get("confidence_threshold", 0.55)
    config["detector"]["confidence_threshold"] = float(threshold)

    classes = config["detector"]["classes"]
    sign_colors = dict((label, spec.get("led"))
                       for label, spec in classes.items())
    gpio_config = config["gpio"]

    display = not args.no_window and bool(os.environ.get("DISPLAY"))
    if not args.no_window and not display:
        print("[WARN] DISPLAY tidak tersedia; jendela lokal dilewati.")

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    camera = None
    leds = None
    server = None
    try:
        camera = open_camera(config, kind=args.camera,
                             sensor_id=args.sensor_id,
                             usb_index=args.usb_index, flip=args.flip)
        detector = SignDetector(config)
        decision = DecisionLogic(
            threshold=threshold,
            stable_frames=config["decision"].get("stable_frames", 5),
            missing_frames=config["decision"].get("missing_frames", 8))
        leds = LedController(
            pins=gpio_config["pins"],
            sign_colors=sign_colors,
            active_high=gpio_config.get("active_high", True),
            mode=gpio_config.get("mode", "BOARD"),
            safe_state=gpio_config.get("safe_state", "all_off"),
            blink_hz=gpio_config.get("blink_hz", 2.0),
            simulate=args.simulate_gpio,
            logger=lambda message: print("[GPIO] %s" % message))

        url = None
        if not args.no_stream:
            server = LiveStreamServer(host=args.host, port=args.port).start()
            port = server.address[1]
            if args.host in ("0.0.0.0", "::"):
                url = "http://%s:%d/" % (_local_ip(), port)
            else:
                url = "http://%s:%d/" % (args.host, port)

        print("=" * 68)
        print(" Jetson Live Camera")
        print(" Kamera    : %s" % type(camera).__name__)
        print(" Threshold : %.2f" % threshold)
        print(" Window    : %s" % ("on" if display else "off"))
        print(" Stream    : %s" % (url or "off"))
        print(" GPIO      : %s" % ("simulasi" if args.simulate_gpio
                                   else "hardware"))
        print(" Tekan q/ESC di jendela atau Ctrl+C untuk berhenti.")
        print("=" * 68)

        start = time.time()
        last_status = 0.0
        last_frame_time = time.time()
        frame_index = 0
        read_failures = 0
        fps = 0.0
        previous_sign = "__init__"
        quality = max(1, min(100, int(args.quality)))

        while not STOP_REQUESTED["value"]:
            frame = camera.read()
            if frame is None:
                read_failures += 1
                if read_failures >= 15:
                    raise CameraError("Kamera tidak memberikan frame "
                                      "(15 kegagalan berturut-turut)")
                time.sleep(0.05)
                continue
            read_failures = 0

            now = time.time()
            detection = detector.detect(frame)
            result = decision.update(detection)
            led_states = leds.apply(result.sign, now=now)

            delta = now - last_frame_time
            last_frame_time = now
            if delta > 0 and frame_index >= 2:
                instant_fps = 1.0 / delta
                fps = instant_fps if fps == 0 else (0.9 * fps +
                                                     0.1 * instant_fps)

            annotated = render_overlay(
                frame, detection, result.sign, result.safe, led_states,
                fps, threshold, result.reason)

            if server is not None:
                stream_frame = annotated
                height, width = stream_frame.shape[:2]
                if args.stream_width > 0 and width > args.stream_width:
                    ratio = args.stream_width / float(width)
                    stream_frame = cv2.resize(
                        stream_frame,
                        (args.stream_width, int(round(height * ratio))),
                        interpolation=cv2.INTER_AREA)
                ok, encoded = cv2.imencode(
                    ".jpg", stream_frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                if ok:
                    server.buffer.publish(encoded.tobytes())

            if display:
                cv2.imshow(WINDOW_NAME, annotated)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
            else:
                time.sleep(0.001)

            elapsed = now - start
            if (result.changed or result.sign != previous_sign or
                    now - last_status >= args.status_interval):
                print(_status_line(result, detection, fps, threshold, elapsed))
                last_status = now
            previous_sign = result.sign
            frame_index += 1

            if args.duration > 0 and elapsed >= args.duration:
                break

        elapsed = time.time() - start
        print("-" * 68)
        print("Selesai: %d frame dalam %.1f detik (%.1f FPS rata-rata)" % (
            frame_index, elapsed,
            frame_index / elapsed if elapsed > 0 else 0.0))
        return 0

    except CameraError as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 2
    except Exception as exc:
        print("[ERROR] %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1
    finally:
        if server is not None:
            server.stop()
        if leds is not None:
            leds.close()
        if camera is not None:
            camera.release()
        if display:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    sys.exit(main())
