#!/usr/bin/env python3
"""Real-camera evaluation matrix (3 signs x 3 distances x 2 lighting).

Examples:
    # One condition
    python3 tools/evaluate_camera.py --sign STOP --distance 1.0m \
        --lighting terang --seconds 4

    # All 18 conditions, guided wizard
    python3 tools/evaluate_camera.py --all

Results are appended to results/evaluation_camera.csv and an annotated
screenshot of each condition is stored in results/screenshots/.
"""

import argparse
import csv
import datetime
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import cv2

from signrec.camera import CameraError, open_camera
from signrec.config import ensure_dir, load_config, resolve_path
from signrec.detector import SignDetector
from signrec.overlay import render_overlay

SIGNS = ("STOP", "SLOW", "GO")
DISTANCES = ("0.5m", "1.0m", "1.5m")
LIGHTING = ("terang", "redup")
LED_BY_SIGN = {"STOP": "red", "SLOW": "yellow", "GO": "green"}


def _safe_name(text):
    return text.replace(".", "_").replace(" ", "_")


def _annotate(frame, detection, threshold):
    accepted = detection is not None and detection.confidence >= threshold
    active = detection.label if accepted else None
    leds = {"red": 0, "yellow": 0, "green": 0}
    if active:
        leds[LED_BY_SIGN[active]] = 1
    return render_overlay(frame, detection, active, not accepted, leds, 0.0,
                          threshold, "camera evaluation")


def _run_condition(camera, detector, sign, distance, lighting, seconds,
                   preview, screenshot_dir, threshold):
    frames = 0
    correct = 0
    detections = 0
    confidences = []
    best = None
    best_conf = -1.0
    start = time.time()
    end = start + seconds

    while time.time() < end:
        frame = camera.read()
        if frame is None:
            time.sleep(0.02)
            continue
        detection = detector.detect(frame)
        frames += 1
        if detection is not None:
            detections += 1
            confidences.append(detection.confidence)
            if (detection.label == sign and
                    detection.confidence >= threshold):
                correct += 1
                if detection.confidence > best_conf:
                    best_conf = detection.confidence
                    best = _annotate(frame, detection, threshold)
        if best is None:
            best = _annotate(frame, detection, threshold)
        if preview:
            cv2.imshow("Evaluate", _annotate(frame, detection, threshold))
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break

    accuracy = correct / float(frames) if frames else 0.0
    mean_conf = (sum(confidences) / len(confidences)) if confidences else 0.0
    path = None
    if best is not None:
        ensure_dir(screenshot_dir)
        path = os.path.join(
            screenshot_dir, "real_%s_%s_%s.jpg" % (
                _safe_name(sign), _safe_name(distance), lighting))
        cv2.imwrite(path, best, [int(cv2.IMWRITE_JPEG_QUALITY), 88])

    row = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sign": sign,
        "distance": distance,
        "lighting": lighting,
        "frames": frames,
        "correct": correct,
        "detections": detections,
        "accuracy": accuracy,
        "mean_confidence": mean_conf,
        "screenshot": path or "",
    }
    return row


def _append_csv(path, row):
    ensure_dir(os.path.dirname(path))
    exists = os.path.exists(path)
    with open(path, "a") as handle:
        writer = csv.writer(handle)
        if not exists:
            writer.writerow(["timestamp", "sign", "distance", "lighting",
                             "frames", "correct", "detections", "accuracy",
                             "mean_confidence", "screenshot"])
        writer.writerow([row["timestamp"], row["sign"], row["distance"],
                         row["lighting"], row["frames"], row["correct"],
                         row["detections"], "%.4f" % row["accuracy"],
                         "%.4f" % row["mean_confidence"],
                         row["screenshot"]])


def main():
    parser = argparse.ArgumentParser(description="Real camera evaluation")
    parser.add_argument("--config", default=None)
    parser.add_argument("--camera", choices=("csi", "usb"), default=None)
    parser.add_argument("--sensor-id", type=int, default=None)
    parser.add_argument("--flip", choices=("none", "horizontal", "vertical",
                                           "rotate180"), default=None)
    parser.add_argument("--sign", choices=SIGNS, default=None)
    parser.add_argument("--distance", choices=DISTANCES, default=None)
    parser.add_argument("--lighting", choices=LIGHTING, default=None)
    parser.add_argument("--seconds", type=float, default=4.0)
    parser.add_argument("--all", action="store_true",
                        help="Run all 18 conditions with prompts")
    parser.add_argument("--no-prompt", action="store_true",
                        help="Do not wait for Enter before each capture")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    detector = SignDetector(config)
    threshold = detector.threshold
    camera = open_camera(config, kind=args.camera, sensor_id=args.sensor_id,
                         flip=args.flip)

    if args.preview and not os.environ.get("DISPLAY"):
        print("[WARN] --preview diabaikan karena DISPLAY tidak tersedia")
        args.preview = False

    if args.all:
        conditions = [(sign, distance, lighting)
                      for lighting in LIGHTING
                      for distance in DISTANCES
                      for sign in SIGNS]
    elif args.sign and args.distance and args.lighting:
        conditions = [(args.sign, args.distance, args.lighting)]
    else:
        print("Berikan --sign/--distance/--lighting, atau gunakan --all.")
        print("Contoh: python3 tools/evaluate_camera.py --all")
        camera.release()
        return 2

    csv_path = resolve_path("results/evaluation_camera.csv")
    screenshot_dir = resolve_path("results/screenshots")
    summary = []

    try:
        print("=" * 74)
        print(" EVALUASI KAMERA NYATA")
        print(" Threshold: %.2f | Durasi: %.1f s per kondisi" % (
            threshold, args.seconds))
        print("=" * 74)
        for index, (sign, distance, lighting) in enumerate(conditions, 1):
            print("")
            print("[%d/%d] %s | jarak %s | cahaya %s" % (
                index, len(conditions), sign, distance, lighting))
            if not args.no_prompt:
                try:
                    input("  Posisikan sign lalu tekan Enter...")
                except EOFError:
                    print("  (stdin tidak interaktif, lanjut otomatis)")
            row = _run_condition(
                camera, detector, sign, distance, lighting,
                args.seconds, args.preview, screenshot_dir, threshold)
            _append_csv(csv_path, row)
            summary.append(row)
            print("  frame=%d benar=%d akurasi=%.0f%% mean_conf=%.3f" % (
                row["frames"], row["correct"], row["accuracy"] * 100,
                row["mean_confidence"]))
            if row["screenshot"]:
                print("  screenshot: %s" % row["screenshot"])
    finally:
        camera.release()
        if args.preview:
            cv2.destroyAllWindows()

    if summary:
        total_correct = sum(row["correct"] for row in summary)
        total_frames = sum(row["frames"] for row in summary)
        print("")
        print("=" * 74)
        print(" TOTAL: %.1f%% (%d/%d frame)" % (
            100.0 * total_correct / total_frames if total_frames else 0.0,
            total_correct, total_frames))
        print(" CSV: %s" % csv_path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CameraError as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        sys.exit(2)
