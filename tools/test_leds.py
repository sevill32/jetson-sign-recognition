#!/usr/bin/env python3
"""Cycle the three LEDs to verify wiring.

Usage:
    python3 tools/test_leds.py
    python3 tools/test_leds.py --simulate
"""

import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from signrec.config import load_config
from signrec.gpio_led import LedController

SIGN_BY_COLOR = {"red": "STOP", "yellow": "SLOW", "green": "GO"}


def main():
    parser = argparse.ArgumentParser(description="Cycle LEDs")
    parser.add_argument("--config", default=None)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    config = load_config(args.config)
    gpio = config["gpio"]
    sign_colors = dict((label, spec.get("led"))
                       for label, spec in config["detector"]["classes"].items())
    leds = LedController(
        pins=gpio["pins"], sign_colors=sign_colors,
        active_high=gpio.get("active_high", True),
        mode=gpio.get("mode", "BOARD"),
        safe_state=gpio.get("safe_state", "all_off"),
        blink_hz=gpio.get("blink_hz", 2.0),
        simulate=args.simulate, logger=lambda message: print("[GPIO] %s" % message))

    try:
        for cycle in range(args.cycles):
            print("Siklus %d/%d" % (cycle + 1, args.cycles))
            for color in ("red", "yellow", "green"):
                sign = SIGN_BY_COLOR[color]
                state = leds.apply(sign)
                print("  %-6s (pin %s) -> %s" % (color, leds.pins[color],
                                                 state))
                time.sleep(args.delay)
            leds.all_off()
            print("  all off (safe state)")
            time.sleep(args.delay)
        print("Selesai. Jika ada LED yang tidak menyala, periksa pin, "
              "polaritas, resistor, dan GND bersama.")
        return 0
    finally:
        leds.close()


if __name__ == "__main__":
    sys.exit(main())
