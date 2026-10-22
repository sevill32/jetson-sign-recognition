#!/usr/bin/env python3
"""Generate printable STOP / SLOW / GO signs.

Usage:
    python3 tools/make_signs.py
    python3 tools/make_signs.py --size 1200
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import cv2

from signrec.config import ensure_dir
from signrec.signs import make_sign


def main():
    parser = argparse.ArgumentParser(description="Generate printable signs")
    parser.add_argument("--size", type=int, default=1000,
                        help="Image width/height in pixels")
    parser.add_argument("--out", default=os.path.join(ROOT, "assets", "signs"),
                        help="Output directory")
    args = parser.parse_args()

    ensure_dir(args.out)
    for label in ("STOP", "SLOW", "GO"):
        image = make_sign(label, size=args.size)
        path = os.path.join(args.out, "%s.png" % label)
        cv2.imwrite(path, image)
        print("OK %s (%dx%d)" % (path, args.size, args.size))
    print("")
    print("Cetak pada kertas A4/A5 dengan lebar minimal 15 cm.")
    print("Tempel di karton agar tidak melengkung saat diuji.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
