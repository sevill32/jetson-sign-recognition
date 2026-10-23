
#!/usr/bin/env python3
"""Test exclusive LED output on Jetson Nano."""

import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from signrec.config import load_config
from signrec.gpio_led import LedController

TEST_SIGNS = ("STOP", "SLOW", "GO")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    if args.cycles < 1 or args.delay < 0:
        parser.error("--cycles harus >= 1 dan --delay harus >= 0")

    config = load_config(args.config)
    gpio = config["gpio"]

    sign_colors = {
        label: spec["led"]
        for label, spec in config["detector"]["classes"].items()
    }

    leds = LedController(
        pins=gpio["pins"],
        sign_colors=sign_colors,
        active_high=gpio.get("active_high", True),
        mode=gpio.get("mode", "BOARD"),
        safe_state=gpio.get("safe_state", "all_off"),
        blink_hz=gpio.get("blink_hz", 2.0),
        simulate=args.simulate,
        logger=lambda msg: print("[GPIO]", msg),
    )

    try:
        print("Mode simulasi:", leds.simulate)
        print("Pin:", leds.pins)

        for cycle in range(args.cycles):
            print("\nSiklus %d/%d" % (cycle + 1, args.cycles))

            for sign in TEST_SIGNS:
                state = leds.apply(sign)
                print("  %-5s -> %s" % (sign, state))
                time.sleep(args.delay)

            state = leds.all_off()
            print("  SAFE  -> %s" % state)
            time.sleep(args.delay)

        print("\nPengujian selesai.")
        return 0

    finally:
        leds.close()


if __name__ == "__main__":
    sys.exit(main())



