import os
import sys
import unittest

import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from signrec.config import load_config
from signrec.detector import SignDetector
from signrec.signs import render_scene


class DetectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = SignDetector(load_config())
        cls.threshold = cls.detector.threshold

    def _check_scene(self, label, scale, brightness, rotation=0.0,
                     offset=(0.0, 0.0), seed=1):
        frame = render_scene(label, scale=scale, brightness=brightness,
                             rotation=rotation, offset=offset, seed=seed)
        detection = self.detector.detect(frame)
        self.assertIsNotNone(detection,
                             "Sign %s tidak terdeteksi" % label)
        self.assertEqual(detection.label, label)
        self.assertGreaterEqual(detection.confidence, self.threshold)
        return detection

    def test_all_signs_normal_light(self):
        for label in ("STOP", "SLOW", "GO"):
            detection = self._check_scene(label, 0.50, 1.0)
            self.assertGreater(detection.confidence, 0.70)

    def test_all_signs_dim_light(self):
        for label in ("STOP", "SLOW", "GO"):
            self._check_scene(label, 0.32, 0.45, rotation=5.0,
                              offset=(0.06, -0.04), seed=4)

    def test_far_signs(self):
        for label in ("STOP", "SLOW", "GO"):
            self._check_scene(label, 0.20, 1.0, rotation=-4.0,
                              offset=(-0.05, 0.03), seed=7)

    def test_blank_scene_returns_none(self):
        for seed in range(4):
            frame = render_scene(None, brightness=1.0, seed=seed)
            self.assertIsNone(self.detector.detect(frame))

    def test_colored_rectangles_are_rejected(self):
        frame = render_scene(None, brightness=1.0, seed=3)
        cv2.rectangle(frame, (200, 80), (440, 260), (0, 210, 210), -1)
        self.assertIsNone(self.detector.detect(frame))
        frame = render_scene(None, brightness=1.0, seed=3)
        cv2.rectangle(frame, (200, 80), (440, 260), (0, 180, 0), -1)
        self.assertIsNone(self.detector.detect(frame))
        frame = render_scene(None, brightness=1.0, seed=3)
        cv2.rectangle(frame, (200, 80), (440, 260), (0, 0, 220), -1)
        self.assertIsNone(self.detector.detect(frame))

    def test_stop_survives_white_balance_shift(self):
        for shift in (-15, 15):
            frame = render_scene("STOP", scale=0.40, brightness=0.55,
                                 seed=11)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(
                "int16")
            hsv[:, :, 0] = (hsv[:, :, 0] + shift) % 180
            frame = cv2.cvtColor(hsv.astype("uint8"), cv2.COLOR_HSV2BGR)
            detection = self.detector.detect(frame)
            self.assertIsNotNone(detection,
                                 "STOP hilang pada hue shift %d" % shift)
            self.assertEqual(detection.label, "STOP")
            self.assertGreaterEqual(detection.confidence, self.threshold)

    def test_bbox_maps_back_to_original_frame(self):
        frame = render_scene("STOP", frame_size=(1280, 720), scale=0.40,
                             brightness=1.0, seed=2)
        detection = self.detector.detect(frame)
        self.assertIsNotNone(detection)
        x, y, w, h = detection.bbox
        self.assertGreater(w, 100)
        self.assertGreaterEqual(x, 0)
        self.assertLessEqual(x + w, 1280)
        self.assertLessEqual(y + h, 720)

    def test_detection_serializable(self):
        detection = self._check_scene("GO", 0.45, 1.0)
        data = detection.as_dict()
        self.assertEqual(data["label"], "GO")
        self.assertIn("confidence", data)


if __name__ == "__main__":
    unittest.main()
