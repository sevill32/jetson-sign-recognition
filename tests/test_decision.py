import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from signrec.decision import DecisionLogic
from signrec.detector import Detection


def detection(label, confidence):
    return Detection(label, confidence, (10, 10, 50, 50), (35, 35),
                     "octagon", "red", 8, 0.8, 0.9, 2000)


class DecisionTest(unittest.TestCase):
    def setUp(self):
        self.logic = DecisionLogic(threshold=0.55, stable_frames=3,
                                   missing_frames=2)

    def test_initial_state_is_safe(self):
        result = self.logic.update(None)
        self.assertTrue(result.safe)
        self.assertIsNone(result.sign)

    def test_requires_stable_frames(self):
        first = self.logic.update(detection("STOP", 0.90))
        self.assertTrue(first.safe)
        second = self.logic.update(detection("STOP", 0.90))
        self.assertTrue(second.safe)
        third = self.logic.update(detection("STOP", 0.90))
        self.assertFalse(third.safe)
        self.assertEqual(third.sign, "STOP")
        self.assertTrue(third.changed)

    def test_low_confidence_never_activates(self):
        for _ in range(10):
            result = self.logic.update(detection("SLOW", 0.40))
            self.assertTrue(result.safe)
        self.assertIsNone(self.logic.active_sign)

    def test_missing_frames_go_to_safe(self):
        for _ in range(3):
            self.logic.update(detection("GO", 0.85))
        self.assertEqual(self.logic.active_sign, "GO")
        first_missing = self.logic.update(None)
        self.assertEqual(first_missing.sign, "GO")
        second_missing = self.logic.update(None)
        self.assertTrue(second_missing.safe)
        self.assertTrue(second_missing.changed)

    def test_sign_transition(self):
        for _ in range(3):
            self.logic.update(detection("STOP", 0.90))
        for _ in range(3):
            result = self.logic.update(detection("SLOW", 0.80))
        self.assertEqual(result.sign, "SLOW")

    def test_below_threshold_drops_active_sign(self):
        for _ in range(3):
            self.logic.update(detection("STOP", 0.90))
        self.logic.update(detection("STOP", 0.30))
        result = self.logic.update(detection("STOP", 0.30))
        self.assertTrue(result.safe)


if __name__ == "__main__":
    unittest.main()
