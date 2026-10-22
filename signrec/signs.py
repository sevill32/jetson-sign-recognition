"""Generate synthetic traffic signs and test scenes.

Used by the printable sign generator, the synthetic benchmark and the unit
tests so that every component shares exactly the same drawing code.
"""

import cv2
import numpy as np

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (0, 0, 215)
YELLOW = (0, 215, 215)
GREEN = (0, 165, 0)
PAPER = (245, 245, 245)


def _octagon(cx, cy, radius):
    points = []
    for index in range(8):
        angle = np.pi / 8.0 + index * np.pi / 4.0
        points.append((int(round(cx + radius * np.cos(angle))),
                       int(round(cy + radius * np.sin(angle)))))
    return np.array(points, dtype=np.int32)


def _text_fit(image, text, center, max_width, color, thickness=5,
              font=cv2.FONT_HERSHEY_DUPLEX, max_scale=3.5):
    """Draw text as large as possible without exceeding max_width."""
    scale = max_scale
    while scale > 0.5:
        (text_w, text_h), baseline = cv2.getTextSize(text, font, scale, thickness)
        if text_w <= max_width:
            break
        scale -= 0.1
    (text_w, text_h), baseline = cv2.getTextSize(text, font, scale, thickness)
    origin = (int(center[0] - text_w / 2.0),
              int(center[1] + text_h / 2.0))
    cv2.putText(image, text, origin, font, scale, color, thickness, cv2.LINE_AA)
    return image


def make_sign(label, size=800):
    """Create a square sign image (BGR) for STOP, SLOW or GO."""
    label = label.upper()
    image = np.full((size, size, 3), PAPER, dtype=np.uint8)
    center = (size // 2, size // 2)

    if label == "STOP":
        outer = _octagon(center[0], center[1], int(size * 0.44))
        inner = _octagon(center[0], center[1], int(size * 0.37))
        cv2.fillPoly(image, [outer], RED, cv2.LINE_AA)
        cv2.polylines(image, [inner], True, WHITE,
                      max(2, int(size * 0.022)), cv2.LINE_AA)
        _text_fit(image, "STOP", (center[0], center[1] + int(size * 0.01)),
                  int(size * 0.56), WHITE, thickness=max(3, int(size * 0.011)),
                  max_scale=size / 230.0)
        return image

    if label == "SLOW":
        triangle = np.array([
            [center[0], int(size * 0.10)],
            [int(size * 0.925), int(size * 0.87)],
            [int(size * 0.075), int(size * 0.87)]
        ], dtype=np.int32)
        cv2.fillPoly(image, [triangle], YELLOW, cv2.LINE_AA)
        cv2.polylines(image, [triangle], True, BLACK,
                      max(3, int(size * 0.025)), cv2.LINE_AA)
        _text_fit(image, "SLOW", (center[0], int(size * 0.67)),
                  int(size * 0.42), BLACK, thickness=max(3, int(size * 0.008)),
                  max_scale=size / 260.0)
        return image

    if label == "GO":
        cv2.circle(image, center, int(size * 0.44), GREEN, -1, cv2.LINE_AA)
        cv2.circle(image, center, int(size * 0.36), WHITE,
                   max(2, int(size * 0.018)), cv2.LINE_AA)
        _text_fit(image, "GO", (center[0], center[1]),
                  int(size * 0.30), WHITE, thickness=max(3, int(size * 0.012)),
                  max_scale=size / 200.0)
        return image

    raise ValueError("Unknown sign label: %s" % label)


def _background(width, height, seed=0):
    rng = np.random.RandomState(seed)
    gradient = np.linspace(55, 175, height, dtype=np.float32)
    base = np.zeros((height, width, 3), dtype=np.float32)
    base[:, :, 0] = gradient[:, None]
    base[:, :, 1] = gradient[:, None]
    base[:, :, 2] = gradient[:, None]
    base += rng.normal(0.0, 5.0, base.shape)
    return base


def render_scene(label, frame_size=(640, 360), scale=0.35, brightness=1.0,
                 seed=0, rotation=0.0, offset=(0.0, 0.0), blur=False):
    """Render a sign on a synthetic background.

    scale      : sign image height / frame height
    brightness : multiplier for the whole scene (1.0 = normal, 0.45 = dim)
    offset     : relative offset (dx, dy) in frame units, e.g. (0.1, -0.05)
    """
    width, height = frame_size
    rng = np.random.RandomState(seed)
    scene = _background(width, height, seed=seed)

    if label is None:
        scene = np.clip(scene * brightness, 0, 255).astype(np.uint8)
        return scene

    sign_size = max(24, int(round(scale * height)))
    sign = make_sign(label, size=sign_size)
    if abs(rotation) > 0.01:
        matrix = cv2.getRotationMatrix2D((sign_size / 2.0, sign_size / 2.0),
                                         rotation, 1.0)
        sign = cv2.warpAffine(sign, matrix, (sign_size, sign_size),
                              borderValue=PAPER)
    if blur or scale < 0.24:
        sign = cv2.GaussianBlur(sign, (3, 3), 0)

    center_x = int(width / 2.0 + offset[0] * width)
    center_y = int(height / 2.0 + offset[1] * height)
    x0 = max(0, min(width - sign_size, center_x - sign_size // 2))
    y0 = max(0, min(height - sign_size, center_y - sign_size // 2))
    scene[y0:y0 + sign_size, x0:x0 + sign_size] = sign.astype(np.float32)

    scene *= brightness
    scene += rng.normal(0.0, 4.0, scene.shape)
    return np.clip(scene, 0, 255).astype(np.uint8)
