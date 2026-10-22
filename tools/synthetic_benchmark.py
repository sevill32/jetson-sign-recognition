#!/usr/bin/env python3
"""Synthetic distance / lighting benchmark.

Renders the three signs at three scales (near, mid, far) under two lighting
conditions, runs the real detector and writes CSV + markdown + annotated
screenshots. This validates the software pipeline without physical signs;
the real-camera matrix is executed with tools/evaluate_camera.py.
"""

import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import cv2
import numpy as np

from signrec.config import ensure_dir, load_config, resolve_path
from signrec.detector import SignDetector
from signrec.overlay import render_overlay
from signrec.signs import render_scene

SCALES = {"dekat": 0.55, "sedang": 0.32, "jauh": 0.20}
LIGHTING = {"terang": 1.0, "redup": 0.45}
LABELS = ("STOP", "SLOW", "GO")
VARIANTS = (
    (0.0, (0.00, 0.00)),
    (6.0, (0.08, -0.04)),
    (-7.0, (-0.07, 0.05)),
)


def _annotate(frame, detection, threshold):
    accepted = detection is not None and detection.confidence >= threshold
    active = detection.label if accepted else None
    leds = {"red": 0, "yellow": 0, "green": 0}
    if active:
        leds[{"STOP": "red", "SLOW": "yellow", "GO": "green"}[active]] = 1
    return render_overlay(frame, detection, active, not accepted, leds, 0.0,
                          threshold, "synthetic")


def main():
    parser = argparse.ArgumentParser(description="Synthetic benchmark")
    parser.add_argument("--config", default=None)
    parser.add_argument("--out", default=None,
                        help="Output directory (default results/synthetic)")
    args = parser.parse_args()

    config = load_config(args.config)
    detector = SignDetector(config)
    threshold = detector.threshold
    output_dir = args.out or resolve_path("results/synthetic")
    ensure_dir(output_dir)

    rows = []
    total = 0
    correct_total = 0

    print("=" * 74)
    print(" SYNTHETIC BENCHMARK  (threshold %.2f)" % threshold)
    print("=" * 74)

    for lighting, brightness in LIGHTING.items():
        ensure_dir(os.path.join(output_dir, lighting))
        for scale_name, scale in SCALES.items():
            for label in LABELS:
                frames = 0
                correct = 0
                confidences = []
                saved = False
                for seed, (rotation, offset) in enumerate(VARIANTS):
                    frame = render_scene(
                        label, scale=scale, brightness=brightness,
                        seed=seed + 10, rotation=rotation, offset=offset)
                    detection = detector.detect(frame)
                    frames += 1
                    if detection is not None:
                        confidences.append(detection.confidence)
                    if (detection is not None and
                            detection.label == label and
                            detection.confidence >= threshold):
                        correct += 1
                    if not saved:
                        annotated = _annotate(frame, detection, threshold)
                        path = os.path.join(output_dir, lighting,
                                            "%s_%s.jpg" % (label, scale_name))
                        cv2.imwrite(path, annotated,
                                    [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                        saved = True
                total += frames
                correct_total += correct
                accuracy = correct / float(frames)
                mean_conf = float(np.mean(confidences)) if confidences else 0.0
                rows.append({
                    "sign": label,
                    "distance": scale_name,
                    "lighting": lighting,
                    "scale": scale,
                    "frames": frames,
                    "correct": correct,
                    "accuracy": accuracy,
                    "mean_confidence": mean_conf,
                })
                print("  %-6s %-7s %-7s : %d/%d  acc=%.2f  mean_conf=%.3f" % (
                    lighting, scale_name, label, correct, frames, accuracy,
                    mean_conf))

    blank_total = 0
    blank_fp = 0
    print("-" * 74)
    for lighting, brightness in LIGHTING.items():
        for seed in range(5):
            frame = render_scene(None, brightness=brightness, seed=100 + seed)
            detection = detector.detect(frame)
            blank_total += 1
            if detection is not None and detection.confidence >= threshold:
                blank_fp += 1
                print("  FALSE POSITIVE (%s seed %d): %s %.2f" % (
                    lighting, seed, detection.label, detection.confidence))
    print("  Blank/no-sign : %d/%d false positive" % (blank_fp, blank_total))

    csv_path = os.path.join(output_dir, "benchmark.csv")
    with open(csv_path, "w") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sign", "distance", "lighting", "scale", "frames",
                         "correct", "accuracy", "mean_confidence"])
        for row in rows:
            writer.writerow([row["sign"], row["distance"], row["lighting"],
                             row["scale"], row["frames"], row["correct"],
                             "%.4f" % row["accuracy"],
                             "%.4f" % row["mean_confidence"]])

    overall = correct_total / float(total) if total else 0.0
    summary_path = os.path.join(output_dir, "summary.md")
    with open(summary_path, "w") as handle:
        handle.write("# Hasil Synthetic Benchmark\n\n")
        handle.write("Threshold confidence: **%.2f**\n\n" % threshold)
        handle.write("| Pencahayaan | Jarak | Sign | Benar | Akurasi | "
                     "Mean confidence |\n")
        handle.write("|---|---|---|---|---|---|\n")
        for row in rows:
            handle.write("| %s | %s | %s | %d/%d | %.0f%% | %.3f |\n" % (
                row["lighting"], row["distance"], row["sign"],
                row["correct"], row["frames"], row["accuracy"] * 100,
                row["mean_confidence"]))
        handle.write("\n**Akurasi total: %.0f%% (%d/%d frame).**\n\n" % (
            overall * 100, correct_total, total))
        handle.write("Kondisi tanpa sign: **%d/%d false positive**.\n\n" % (
            blank_fp, blank_total))
        handle.write("Screenshot beranotasi: `results/synthetic/<cahaya>/`.\n")

    print("=" * 74)
    print(" AKURASI TOTAL : %.1f%% (%d/%d)" % (overall * 100, correct_total,
                                               total))
    print(" FALSE POSITIVE: %d/%d" % (blank_fp, blank_total))
    print(" CSV           : %s" % csv_path)
    print(" Ringkasan     : %s" % summary_path)
    print(" Screenshot    : %s" % output_dir)
    return 0 if overall >= 0.90 and blank_fp == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
