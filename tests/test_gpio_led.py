import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from signrec.gpio_led import LedController

PINS = {"red": 18, "yellow": 12, "green": 16}
SIGN_COLORS = {"STOP": "red", "SLOW": "yellow", "GO": "green"}


class GpioLedTest(unittest.TestCase):
    def setUp(self):
        self.leds = LedController(PINS, SIGN_COLORS, simulate=True,
                                  safe_state="all_off")

    def tearDown(self):
        self.leds.close()

    def test_stop_turns_red_only(self):
        states = self.leds.apply("STOP", now=0.0)
        self.assertEqual(states, {"red": 1, "yellow": 0, "green": 0})

    def test_each_sign_maps_to_its_led(self):
        for sign, color in SIGN_COLORS.items():
            states = self.leds.apply(sign, now=0.0)
            self.assertEqual(states[color], 1)
            for other in PINS:
                if other != color:
                    self.assertEqual(states[other], 0)

    def test_safe_state_turns_all_off(self):
        self.leds.apply("GO", now=0.0)
        states = self.leds.apply(None, now=0.0)
        self.assertEqual(states, {"red": 0, "yellow": 0, "green": 0})

    def test_blink_yellow_safe_state(self):
        leds = LedController(PINS, SIGN_COLORS, simulate=True,
                             safe_state="blink_yellow", blink_hz=2.0)
        try:
            self.assertEqual(leds.apply(None, now=0.00)["yellow"], 1)
            self.assertEqual(leds.apply(None, now=0.30)["yellow"], 0)
            self.assertEqual(leds.apply(None, now=0.55)["yellow"], 1)
        finally:
            leds.close()

    def test_status_text(self):
        self.leds.apply("SLOW", now=0.0)
        self.assertEqual(self.leds.status_text(), "R=0 Y=1 G=0")


if __name__ == "__main__":
    unittest.main()
