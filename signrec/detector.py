import cv2
import numpy as np


class Detection:
    def __init__(
        self,
        label,
        confidence,
        bbox,
        center,
        shape,
        color,
        vertices,
        circularity,
        solidity,
        area,
    ):
        self.label = label
        self.confidence = confidence
        self.bbox = bbox
        self.center = center
        self.shape = shape
        self.color = color
        self.vertices = vertices
        self.circularity = circularity
        self.solidity = solidity
        self.area = area


class SignDetector:
    def __init__(self, config):
        detector_cfg = config.get("detector", {})
        camera_cfg = config.get("camera", {})

        self.threshold = float(
            detector_cfg.get("confidence_threshold", 0.75)
        )
        self.min_area_ratio = float(
            detector_cfg.get("min_area_ratio", 0.003)
        )
        self.max_contours = int(
            detector_cfg.get("max_contours", 15)
        )
        self.blur_ksize = int(
            detector_cfg.get("blur_ksize", 5)
        )
        self.morph_ksize = int(
            detector_cfg.get("morph_ksize", 5)
        )
        self.process_width = int(
            camera_cfg.get("process_width", 640)
        )

        weights = detector_cfg.get("weights", {})
        self.w_shape = float(weights.get("shape", 0.65))
        self.w_color = float(weights.get("color", 0.20))
        self.w_area = float(weights.get("area", 0.15))

        total = self.w_shape + self.w_color + self.w_area
        if total <= 0:
            self.w_shape = 0.65
            self.w_color = 0.20
            self.w_area = 0.15
        else:
            self.w_shape /= total
            self.w_color /= total
            self.w_area /= total

        self.classes = detector_cfg.get("classes", {})
        self.colors = config.get("colors", {})

        # Dua rentang HSV untuk merah.
        self.default_red_ranges = [
            [0, 90, 60, 10, 255, 255],
            [170, 90, 60, 179, 255, 255],
        ]

        kernel_size = max(3, self.morph_ksize)
        if kernel_size % 2 == 0:
            kernel_size += 1

        self.kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (kernel_size, kernel_size),
        )

    def detect(self, frame):
        if frame is None or not isinstance(frame, np.ndarray):
            return None

        if frame.ndim != 3 or frame.size == 0:
            return None

        original_h, original_w = frame.shape[:2]

        if original_h <= 0 or original_w <= 0:
            return None

        if self.process_width > 0 and original_w > self.process_width:
            scale = self.process_width / float(original_w)
            work = cv2.resize(
                frame,
                (
                    self.process_width,
                    max(1, int(original_h * scale)),
                ),
                interpolation=cv2.INTER_AREA,
            )
        else:
            work = frame.copy()

        work_h, work_w = work.shape[:2]
        frame_area = float(work_h * work_w)

        blur_size = max(1, self.blur_ksize)
        if blur_size % 2 == 0:
            blur_size += 1

        if blur_size > 1:
            work = cv2.GaussianBlur(
                work, (blur_size, blur_size), 0
            )

        hsv = cv2.cvtColor(work, cv2.COLOR_BGR2HSV)

        classes = self.classes or {
            "STOP": {"color": "red", "shape": "octagon"},
            "SLOW": {"color": "yellow", "shape": "triangle"},
            "GO": {"color": "green", "shape": "circle"},
        }

        best = None
        best_confidence = 0.0

        for label, spec in classes.items():
            if not isinstance(spec, dict):
                continue

            color_name = str(spec.get("color", "")).lower()
            shape = str(spec.get("shape", "")).lower()

            if not color_name or not shape:
                continue

            mask = self._color_mask(hsv, color_name)

            if mask is None or cv2.countNonZero(mask) == 0:
                continue

            mask = cv2.morphologyEx(
                mask, cv2.MORPH_OPEN, self.kernel, iterations=1
            )
            mask = cv2.morphologyEx(
                mask, cv2.MORPH_CLOSE, self.kernel, iterations=2
            )

            contours_result = cv2.findContours(
                mask,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            contours = contours_result[-2]

            contours = sorted(
                contours, key=cv2.contourArea, reverse=True
            )

            for contour in contours[:self.max_contours]:
                candidate = self._evaluate(
                    contour,
                    frame_area,
                    str(label),
                    color_name,
                    shape,
                )

                if candidate is None:
                    continue

                # Threshold digunakan sebelum hasil diterima.
                if candidate.confidence < self.threshold:
                    continue

                if candidate.confidence > best_confidence:
                    best = candidate
                    best_confidence = candidate.confidence

        if best is None:
            return None

        sx = original_w / float(work_w)
        sy = original_h / float(work_h)

        x, y, w, h = best.bbox
        x = int(round(x * sx))
        y = int(round(y * sy))
        w = int(round(w * sx))
        h = int(round(h * sy))

        best.bbox = (x, y, w, h)
        best.center = (x + w // 2, y + h // 2)

        return best

    def _color_mask(self, hsv, color_name):
        ranges = self.colors.get(color_name, [])

        if isinstance(ranges, dict):
            ranges = [ranges]

        if not isinstance(ranges, (list, tuple)):
            ranges = []

        ranges = list(ranges)

        # Gabungkan rentang merah standar dengan konfigurasi.
        if color_name in ("red", "merah"):
            ranges.extend(self.default_red_ranges)

        combined = np.zeros(hsv.shape[:2], dtype=np.uint8)

        for item in ranges:
            try:
                if isinstance(item, dict):
                    lower = item.get("lower")
                    upper = item.get("upper")

                    if lower is None or upper is None:
                        continue

                    lower = np.array(lower, dtype=np.uint8)
                    upper = np.array(upper, dtype=np.uint8)

                elif isinstance(item, (list, tuple)) and len(item) == 6:
                    values = [int(v) for v in item]
                    lower = np.array(values[:3], dtype=np.uint8)
                    upper = np.array(values[3:], dtype=np.uint8)

                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    lower = np.array(item[0], dtype=np.uint8)
                    upper = np.array(item[1], dtype=np.uint8)

                else:
                    continue

                current = cv2.inRange(hsv, lower, upper)
                combined = cv2.bitwise_or(combined, current)

            except (TypeError, ValueError, OverflowError):
                continue

        return combined

    def _evaluate(
        self, contour, frame_area, label, color, shape
    ):
        area = float(cv2.contourArea(contour))

        if frame_area <= 0:
            return None

        if area < self.min_area_ratio * frame_area:
            return None

        x, y, w, h = cv2.boundingRect(contour)

        if w < 12 or h < 12:
            return None

        aspect = w / float(h)

        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            return None

        hull = cv2.convexHull(contour)
        hull_area = float(cv2.contourArea(hull))

        if hull_area <= 0:
            return None

        solidity = min(1.0, area / hull_area)
        circularity = min(
            1.0,
            (4.0 * np.pi * area) / (perimeter * perimeter),
        )

        hull_perimeter = cv2.arcLength(hull, True)
        approx = cv2.approxPolyDP(
            hull, 0.025 * hull_perimeter, True
        )
        vertices = len(approx)

        if solidity < 0.55:
            return None

        shape_score = self._shape_score(
            shape, vertices, circularity, solidity, aspect
        )

        if shape_score <= 0:
            return None

        area_ratio = area / frame_area
        area_score = min(
            1.0,
            max(
                0.0,
                area_ratio / max(self.min_area_ratio * 8, 1e-6),
            ),
        )

        confidence = (
            self.w_shape * shape_score
            + self.w_color
            + self.w_area * area_score
        )
        confidence = float(np.clip(confidence, 0.0, 1.0))

        return Detection(
            label=label,
            confidence=confidence,
            bbox=(int(x), int(y), int(w), int(h)),
            center=(int(x + w // 2), int(y + h // 2)),
            shape=shape,
            color=color,
            vertices=int(vertices),
            circularity=float(circularity),
            solidity=float(solidity),
            area=area,
        )

    @staticmethod
    def _shape_score(
        shape, vertices, circularity, solidity, aspect
    ):
        shape = shape.lower()

        if shape in ("octagon", "octagonal", "stop"):
            # STOP harus menyerupai oktagon.
            if vertices == 8:
                score = 1.00
            elif vertices in (7, 9):
                score = 0.80
            elif vertices in (6, 10):
                score = 0.50
            else:
                return 0.0

            if not 0.70 <= aspect <= 1.30:
                return 0.0

            if solidity < 0.70:
                return 0.0

            return score

        if shape in ("triangle", "triangular"):
            if vertices == 3:
                score = 1.0
            elif vertices in (4, 5):
                score = 0.65
            else:
                return 0.0

            if not 0.55 <= aspect <= 1.50:
                return 0.0

            return score

        if shape in ("circle", "round"):
            if circularity >= 0.82:
                score = 1.0
            elif circularity >= 0.72:
                score = 0.80
            else:
                return 0.0

            if not 0.70 <= aspect <= 1.30:
                return 0.0

            if solidity < 0.70:
                return 0.0

            return score

        return 0.0



