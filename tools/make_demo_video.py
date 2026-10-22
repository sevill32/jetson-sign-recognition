#!/usr/bin/env python3
"""Create a repeatable demo video: STOP -> SLOW -> GO -> no sign.

The video is used to exercise the complete Camera -> Detection -> Decision ->
GPIO(simulation) -> LED pipeline without physical signs.
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import cv2
import numpy as np

from signrec.config import ensure_dir
from signrec.signs import render_scene

SEGMENTS = (
    ("STOP", 1.5),
    ("SLOW", 1.5),
    ("GO", 1.5),
    (None, 1.5),
    ("STOP", 1.0),
    (None, 1.0),
)


def main():
    parser = argparse.ArgumentParser(description="Create demo video")
    parser.add_argument("--output", default=os.path.join(
        ROOT, "results", "demo", "demo_signs.mp4"))
    parser.add_argument("--codec", default="mp4v")
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    args = parser.parse_args()

    ensure_dir(os.path.dirname(args.output))
    writer = cv2.VideoWriter(args.output,
                             cv2.VideoWriter_fourcc(*args.codec),
                             args.fps, (args.width, args.height))
    if not writer.isOpened():
        print("[ERROR] VideoWriter gagal dibuka (codec %s)" % args.codec,
              file=sys.stderr)
        return 2

    frame_index = 0
    total = sum(int(round(duration * args.fps)) for _, duration in SEGMENTS)
    for label, duration in SEGMENTS:
        count = int(round(duration * args.fps))
        for index in range(count):
            phase = index / float(max(1, count))
            rotation = 5.0 * np.sin(2.0 * np.pi * phase)
            offset = (0.05 * np.sin(np.pi * phase),
                      -0.03 * np.cos(np.pi * phase))
            brightness = 0.95 + 0.05 * np.sin(2.0 * np.pi * phase)
            frame = render_scene(
                label, frame_size=(args.width, args.height), scale=0.50,
                brightness=brightness, seed=frame_index, rotation=rotation,
                offset=offset)
            writer.write(frame)
            frame_index += 1

    writer.release()
    print("OK %s (%d frame @ %d fps)" % (args.output, total, args.fps))
    print("Jalankan:")
    print("  python3 main.py --camera video --video %s --headless "
          "--simulate-gpio --duration 10" % os.path.relpath(args.output, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
