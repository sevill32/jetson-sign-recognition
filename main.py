#!/usr/bin/env python3
"""Camera -> Sign Recognition -> Decision Logic -> GPIO -> LED.

Run from the repository root:
    python3 main.py
    python3 main.py --headless --simulate-gpio --duration 10
"""

import argparse
import csv
import datetime
import os
import signal
import sys
import time

import cv2

from signrec.camera import CameraError, open_camera
from signrec.config import ensure_dir, load_config, resolve_path
from signrec.decision import DecisionLogic
from signrec.detector import SignDetector
from signrec.gpio_led import LedController
from signrec.overlay import render_overlay

STOP_REQUESTED = {"value": False}


def _handle_signal(signum, frame):
    STOP_REQUESTED["value"] = True


def _timestamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _iso_timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _save_snapshot(image, directory, label, enabled):
    if not enabled:
        return None
    ensure_dir(directory)
    name = "%s_%s.jpg" % (_timestamp(), label or "SAFE")
    path = os.path.join(directory, name)
    cv2.imwrite(path, image, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    return path


def _format_status(result, led_states, fps, threshold, elapsed):
    if result.sign is not None:
        headline = "SIGN=%-5s conf=%.2f" % (result.sign,
                                            result.confidence)
    elif result.candidate is not None:
        headline = "SIGN=--    cand=%-5s conf=%.2f < %.2f" % (
            result.candidate.label, result.candidate.confidence, threshold)
    else:
        headline = "SIGN=--    no detection"
    return "[%s] %s | LED %s | SAFE=%-3s | %.1f FPS | %.1fs" % (
        datetime.datetime.now().strftime("%H:%M:%S"),
        headline,
        "R=%d Y=%d G=%d" % (led_states.get("red", 0),
                            led_states.get("yellow", 0),
                            led_states.get("green", 0)),
        "yes" if result.safe else "no",
        fps,
        elapsed,
    )


def build_parser():
    parser = argparse.ArgumentParser(
        description="Jetson Nano sign recognition and LED controller",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--config", default=None,
                        help="Path to config.json")
    parser.add_argument("--camera", choices=("csi", "usb", "video"),
                        default=None, help="Override camera type")
    parser.add_argument("--sensor-id", type=int, default=None,
                        help="CSI sensor id (nvarguscamerasrc)")
    parser.add_argument("--usb-index", type=int, default=None,
                        help="USB camera index")
    parser.add_argument("--flip", choices=("none", "horizontal", "vertical",
                                           "rotate180"), default=None,
                        help="Flip camera image (for inverted mounting)")
    parser.add_argument("--video", default=None,
                        help="Video file for --camera video (demo/testing)")
    parser.add_argument("--threshold", type=float, default=None,
                        help="Override confidence threshold")
    parser.add_argument("--headless", action="store_true",
                        help="Do not open an OpenCV window")
    parser.add_argument("--show", action="store_true",
                        help="Force an OpenCV window")
    parser.add_argument("--simulate-gpio", action="store_true",
                        help="Do not touch real GPIO pins")
    parser.add_argument("--duration", type=float, default=0.0,
                        help="Stop after N seconds (0 = unlimited)")
    parser.add_argument("--no-snapshot", action="store_true",
                        help="Disable annotated snapshot files")
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
    output_config = config["output"]

    log_dir = resolve_path(output_config.get("log_dir", "results/logs"))
    snapshot_dir = resolve_path(output_config.get("snapshot_dir",
                                                  "results/runtime/snapshots"))
    ensure_dir(log_dir)
    snapshots_enabled = (not args.no_snapshot and
                         output_config.get("snapshot_on_change", True))

    display = args.show or (not args.headless and
                            bool(os.environ.get("DISPLAY")))

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    camera = None
    leds = None
    log_handle = None
    writer = None
    try:
        camera = open_camera(config, kind=args.camera,
                             sensor_id=args.sensor_id,
                             usb_index=args.usb_index, flip=args.flip,
                             video_path=args.video)
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

        log_path = os.path.join(log_dir, "run_%s.csv" % _timestamp())
        log_handle = open(log_path, "w")
        writer = csv.writer(log_handle)
        writer.writerow(["timestamp", "frame", "detected_label",
                         "confidence", "active_sign", "safe", "led_red",
                         "led_yellow", "led_green", "fps"])

        print("=" * 72)
        print(" Jetson Nano Sign Recognition")
        print(" Kamera     : %s" % type(camera).__name__)
        print(" Threshold  : %.2f" % threshold)
        print(" GPIO pins  : %s" % gpio_config["pins"])
        print(" Safe state : %s" % gpio_config.get("safe_state", "all_off"))
        print(" Log        : %s" % log_path)
        print(" Display    : %s" % ("on" if display else "headless"))
        print(" Tekan Ctrl+C untuk berhenti." if display
              else " Jalankan tanpa batas; hentikan dengan Ctrl+C.")
        print("=" * 72)

        start = time.time()
        last_status = 0.0
        frame_index = 0
        read_failures = 0
        fps = 0.0
        last_frame_time = time.time()
        previous_sign = "__init__"
        snapshot_done = False
        safe_reason = ""
        status_interval = float(output_config.get("status_interval", 0.5))
        counts = {"frames": 0, "safe": 0}
        for label in classes:
            counts[label] = 0

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

            if result.changed:
                safe_reason = result.reason
                snapshot = _save_snapshot(
                    annotated, snapshot_dir, result.sign, snapshots_enabled)
                if snapshot:
                    print("[SNAPSHOT] %s" % snapshot)
            if (not snapshot_done and snapshots_enabled and
                    frame_index >= 10):
                _save_snapshot(annotated, snapshot_dir,
                               result.sign or "SAFE", snapshots_enabled)
                snapshot_done = True

            writer.writerow([
                _iso_timestamp(), frame_index,
                detection.label if detection else "",
                "%.4f" % (detection.confidence if detection else 0.0),
                result.sign or "",
                1 if result.safe else 0,
                led_states.get("red", 0),
                led_states.get("yellow", 0),
                led_states.get("green", 0),
                "%.2f" % fps,
            ])
            if frame_index % 30 == 0:
                log_handle.flush()

            elapsed = now - start
            if (result.changed or result.sign != previous_sign or
                    now - last_status >= status_interval):
                print(_format_status(result, led_states, fps, threshold,
                                     elapsed))
                last_status = now
            previous_sign = result.sign

            counts["frames"] += 1
            if result.safe:
                counts["safe"] += 1
            else:
                counts[result.sign] = counts.get(result.sign, 0) + 1
            frame_index += 1

            if display:
                cv2.imshow("Jetson Sign Recognition", annotated)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
            else:
                time.sleep(0.001)

            if args.duration > 0 and elapsed >= args.duration:
                break

        elapsed = time.time() - start
        print("-" * 72)
        print("Selesai: %d frame dalam %.1f detik (%.1f FPS rata-rata)" % (
            counts["frames"], elapsed,
            counts["frames"] / elapsed if elapsed > 0 else 0.0))
        print("Distribusi: SAFE=%d, STOP=%d, SLOW=%d, GO=%d" % (
            counts["safe"], counts.get("STOP", 0), counts.get("SLOW", 0),
            counts.get("GO", 0)))
        print("Log CSV: %s" % log_path)
        return 0

    except CameraError as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 2
    except Exception as exc:
        print("[ERROR] %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1
    finally:
        if leds is not None:
            leds.close()
        if camera is not None:
            camera.release()
        if log_handle is not None:
            log_handle.close()
        if display:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    sys.exit(main())
