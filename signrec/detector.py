"""Colour + shape based traffic sign detector.

The detector is intentionally dependency-free apart from OpenCV and NumPy so
that it runs on the stock JetPack OpenCV 3.2 build (no TensorFlow required).

Pipeline for every frame:
    resize -> blur -> BGR to HSV -> colour mask -> morphology
    -> external contours -> polygon approximation -> shape score
    -> weighted confidence -> best candidate
"""

import math

import cv2
import numpy as np


class Detection(object):
    """A single sign candidate."""

    __slots__ = ("label", "confidence", "bbox", "center", "shape", "color",
                 "vertices", "circularity", "solidity", "area")

    def __init__(self, label, confidence, bbox, center, shape, color,
                 vertices, circularity, solidity, area):
        self.label = label
        self.confidence = float(confidence)
        self.bbox = bbox
        self.center = center
        self.shape = shape
        self.color = color
        self.vertices = int(vertices)
        self.circularity = float(circularity)
        self.solidity = float(solidity)
        self.area = float(area)

    def as_dict(self):
        return {
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "bbox": [int(v) for v in self.bbox],
            "center": [int(v) for v in self.center],
            "shape": self.shape,
            "color": self.color,
            "vertices": self.vertices,
            "circularity": round(self.circularity, 4),
            "solidity": round(self.solidity, 4),
            "area": round(self.area, 1),
        }

    def __repr__(self):
        return "Detection(%s, %.3f, %s)" % (self.label, self.confidence,
                                            self.bbox)


class SignDetector(object):
    def __init__(self, config):
        detector = config["detector"]
        self.threshold = float(detector.get("confidence_threshold", 0.55))
        self.min_area_ratio = float(detector.get("min_area_ratio", 0.003))
        self.max_contours = int(detector.get("max_contours", 6))
        self.blur_ksize = int(detector.get("blur_ksize", 5))
        if self.blur_ksize % 2 == 0:
            self.blur_ksize += 1
        self.morph_ksize = int(detector.get("morph_ksize", 5))
        if self.morph_ksize % 2 == 0:
            self.morph_ksize += 1

        weights = detector.get("weights", {})
        self.w_shape = float(weights.get("shape", 0.55))
        self.w_color = float(weights.get("color", 0.30))
        self.w_area = float(weights.get("area", 0.15))
        total = self.w_shape + self.w_color + self.w_area
        if total <= 0:
            raise ValueError("Detector weights must be positive")
        self.w_shape /= total
        self.w_color /= total
        self.w_area /= total

        self.classes = detector["classes"]
        self.colors = {}
        for name, ranges in config["colors"].items():
            self.colors[name] = [tuple(int(v) for v in item) for item in ranges]

        self.process_width = int(config["camera"].get("process_width", 640))
        self.last_masks = {}
        self._kernel = np.ones((self.morph_ksize, self.morph_ksize),
                               dtype=np.uint8)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect(self, frame):
        """Return the best Detection for a BGR frame, or None."""
        if frame is None or frame.size == 0:
            return None

        original_h, original_w = frame.shape[:2]
        processed = self._preprocess(frame)
        proc_h, proc_w = processed.shape[:2]
        scale_x = original_w / float(proc_w)
        scale_y = original_h / float(proc_h)

        hsv = cv2.cvtColor(processed, cv2.COLOR_BGR2HSV)
        frame_area = float(proc_w * proc_h)
        min_area = self.min_area_ratio * frame_area

        best = None
        self.last_masks = {}

        for label, spec in self.classes.items():
            color_name = spec["color"]
            if color_name not in self.colors:
                continue
            mask = self._color_mask(hsv, color_name)
            self.last_masks[label] = mask

            contours = self._find_contours(mask)
            for contour in contours[:self.max_contours]:
                candidate = self._evaluate(
                    label=label,
                    shape=spec["shape"],
                    color_name=color_name,
                    contour=contour,
                    mask=mask,
                    frame_area=frame_area,
                    min_area=min_area,
                )
                if candidate is None:
                    continue
                if best is None or candidate.confidence > best.confidence:
                    best = candidate

        if best is None:
            return None

        x, y, w, h = best.bbox
        best.bbox = (int(round(x * scale_x)), int(round(y * scale_y)),
                     int(round(w * scale_x)), int(round(h * scale_y)))
        best.center = (best.bbox[0] + best.bbox[2] // 2,
                       best.bbox[1] + best.bbox[3] // 2)
        return best

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _preprocess(self, frame):
        height, width = frame.shape[:2]
        if width > self.process_width:
            ratio = self.process_width / float(width)
            new_size = (self.process_width, int(round(height * ratio)))
            frame = cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)
        if self.blur_ksize > 1:
            frame = cv2.GaussianBlur(frame, (self.blur_ksize, self.blur_ksize),
                                     0)
        return frame

    def _color_mask(self, hsv, color_name):
        mask = None
        for hue_lo, sat_lo, val_lo, hue_hi, sat_hi, val_hi in self.colors[color_name]:
            lower = np.array([hue_lo, sat_lo, val_lo], dtype=np.uint8)
            upper = np.array([hue_hi, sat_hi, val_hi], dtype=np.uint8)
            current = cv2.inRange(hsv, lower, upper)
            if mask is None:
                mask = current
            else:
                mask = cv2.bitwise_or(mask, current)
        if mask is None:
            mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel)
        return mask

    @staticmethod
    def _find_contours(mask):
        result = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                  cv2.CHAIN_APPROX_SIMPLE)
        contours = result[0] if len(result) == 2 else result[1]
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        return contours

    def _evaluate(self, label, shape, color_name, contour, mask, frame_area,
                  min_area):
        area = cv2.contourArea(contour)
        if area < min_area:
            return None

        x, y, w, h = cv2.boundingRect(contour)
        if w < 12 or h < 12:
            return None

        aspect = w / float(h)
        if aspect < 0.55 or aspect > 1.80:
            return None

        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        if hull_area <= 0:
            return None
        solidity = area / hull_area
        if solidity < 0.50:
            return None

        perimeter = cv2.arcLength(hull, True)
        if perimeter <= 0:
            return None

        approx = cv2.approxPolyDP(hull, 0.03 * perimeter, True)
        vertices = len(approx)
        circularity = min(
            1.0, 4.0 * math.pi * hull_area / (perimeter * perimeter))
        extent = area / float(w * h)

        if not self._geometry_ok(shape, aspect, extent, solidity,
                                 circularity):
            return None

        shape_score = self._shape_score(shape, vertices, circularity, extent)
        if shape_score < 0.25:
            return None

        roi = mask[y:y + h, x:x + w]
        density = cv2.countNonZero(roi) / float(max(1, w * h))
        color_score = min(1.0, density / 0.50)

        area_ratio = area / frame_area
        area_score = min(1.0, math.sqrt(area_ratio / 0.03))

        confidence = (self.w_shape * shape_score +
                      self.w_color * color_score +
                      self.w_area * area_score)
        confidence = max(0.0, min(1.0, confidence))

        if confidence < 0.20:
            return None

        return Detection(
            label=label,
            confidence=confidence,
            bbox=(x, y, w, h),
            center=(x + w // 2, y + h // 2),
            shape=shape,
            color=color_name,
            vertices=vertices,
            circularity=circularity,
            solidity=solidity,
            area=area,
        )

    @staticmethod
    def _geometry_ok(shape, aspect, extent, solidity, circularity):
        """Reject rectangles / fragmented blobs before shape scoring."""
        if shape == "triangle":
            if aspect < 0.65 or aspect > 1.45:
                return False
            if extent < 0.32 or extent > 0.72:
                return False
            if solidity < 0.60:
                return False
        elif shape == "octagon":
            if aspect < 0.65 or aspect > 1.45:
                return False
            if extent < 0.55 or extent > 0.96:
                return False
            if solidity < 0.58:
                return False
        elif shape == "circle":
            if aspect < 0.70 or aspect > 1.35:
                return False
            if extent < 0.55 or extent > 0.90:
                return False
            if circularity < 0.80 or solidity < 0.70:
                return False
        return True

    @staticmethod
    def _shape_score(shape, vertices, circularity, extent):
        if shape == "octagon":
            if vertices == 8:
                vertex_score = 1.0
            elif vertices in (7, 9):
                vertex_score = 0.80
            elif vertices in (6, 10):
                vertex_score = 0.45
            else:
                vertex_score = 0.05
            circle_score = max(0.0, 1.0 - abs(circularity - 0.82) / 0.30)
            return 0.80 * vertex_score + 0.20 * circle_score

        if shape == "triangle":
            if vertices == 3:
                vertex_score = 1.0
            elif vertices == 4:
                vertex_score = 0.65
            elif vertices == 5:
                vertex_score = 0.35
            else:
                vertex_score = 0.05
            return vertex_score

        if shape == "circle":
            circle_score = max(0.0, min(1.0, (circularity - 0.55) / 0.30))
            if vertices >= 6:
                vertex_score = 1.0
            elif vertices == 5:
                vertex_score = 0.70
            elif vertices == 4:
                vertex_score = 0.35
            else:
                vertex_score = 0.10
            return 0.75 * circle_score + 0.25 * vertex_score

        return 0.0
