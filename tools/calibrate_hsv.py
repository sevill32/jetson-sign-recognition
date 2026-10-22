#!/usr/bin/env python3
"""Interactive HSV calibration helper (requires a display).

Usage:
    python3 tools/calibrate_hsv.py --color red
    python3 tools/calibrate_hsv.py --color yellow
    python3 tools/calibrate_hsv.py --color green
    python3 tools/calibrate_hsv.py --color red --camera usb

Press "s" to print the current range as JSON, "q" or ESC to quit.
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import cv2
import numpy as np

from signrec.camera import open_camera
from signrec.config import load_config

WINDOW = "HSV Calibration"


def _nothing(value):
    pass


def main():
    parser = argparse.ArgumentParser(description="HSV calibration")
    parser.add_argument("--config", default=None)
    parser.add_argument("--camera", choices=("csi", "usb"), default=None)
    parser.add_argument("--color", choices=("red", "yellow", "green"),
                        default="red")
    parser.add_argument("--sensor-id", type=int, default=None)
    args = parser.parse_args()

    if not os.environ.get("DISPLAY"):
        print("[ERROR] Kalibrasi HSV membutuhkan display (DISPLAY kosong).")
        return 2

    config = load_config(args.config)
    ranges = config["colors"][args.color]
    first = ranges[0]
    lower = [first[0], first[1], first[2]]
    upper = [first[3], first[4], first[5]]

    camera = open_camera(config, kind=args.camera, sensor_id=args.sensor_id)
    cv2.namedWindow(WINDOW)
    for name, value, maximum in (
            ("H min", lower[0], 180), ("S min", lower[1], 255),
            ("V min", lower[2], 255), ("H max", upper[0], 180),
            ("S max", upper[1], 255), ("V max", upper[2], 255)):
        cv2.createTrackbar(name, WINDOW, value, maximum, _nothing)
    cv2.createTrackbar("Open", WINDOW, 1, 1, _nothing)

    print("Warna: %s. Atur trackbar, tekan 's' untuk cetak rentang, "
          "'q' untuk keluar." % args.color)
    try:
        while True:
            frame = camera.read()
            if frame is None:
                continue
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            lo = np.array([
                cv2.getTrackbarPos("H min", WINDOW),
                cv2.getTrackbarPos("S min", WINDOW),
                cv2.getTrackbarPos("V min", WINDOW)], dtype=np.uint8)
            hi = np.array([
                cv2.getTrackbarPos("H max", WINDOW),
                cv2.getTrackbarPos("S max", WINDOW),
                cv2.getTrackbarPos("V max", WINDOW)], dtype=np.uint8)
            mask = cv2.inRange(hsv, lo, hi)
            result = cv2.bitwise_and(frame, frame, mask=mask)
            both = np.hstack((frame, result))
            cv2.imshow(WINDOW, both)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("s"):
                print(json.dumps([[int(v) for v in lo] + [int(v) for v in hi]]))
            elif key in (27, ord("q")):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
