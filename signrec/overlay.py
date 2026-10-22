"""Draw the recognition result and LED status on a frame."""

import cv2

LABEL_COLORS = {
    "STOP": (0, 0, 255),
    "SLOW": (0, 200, 255),
    "GO": (0, 200, 0),
}
SAFE_COLOR = (160, 160, 160)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
LED_COLORS = {
    "red": (0, 0, 255),
    "yellow": (0, 200, 255),
    "green": (0, 200, 0),
}


def _filled_bar(image, top_left, bottom_right, color, alpha=0.65):
    cv2.rectangle(image, top_left, bottom_right, color, -1)


def _draw_text(image, text, position, color=WHITE, scale=0.55, thickness=1):
    cv2.putText(image, text, position, cv2.FONT_HERSHEY_SIMPLEX, scale,
                BLACK, thickness + 2, cv2.LINE_AA)
    cv2.putText(image, text, position, cv2.FONT_HERSHEY_SIMPLEX, scale,
                color, thickness, cv2.LINE_AA)


def render_overlay(frame, detection, active_sign, safe, led_states, fps,
                   threshold, reason=""):
    """Return a copy of frame with detection, decision and LED status."""
    image = frame.copy()
    height, width = image.shape[:2]

    bar_height = max(54, int(height * 0.16))
    _filled_bar(image, (0, 0), (width, bar_height), (20, 20, 20), 0.72)

    if detection is not None:
        x, y, w, h = detection.bbox
        accepted = detection.confidence >= threshold
        color = LABEL_COLORS.get(detection.label, WHITE) if accepted else SAFE_COLOR
        cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
        text = "%s %.2f" % (detection.label, detection.confidence)
        if not accepted:
            text += " < thr"
        text_y = max(18, y - 8)
        _draw_text(image, text, (x, text_y), color, 0.52, 1)

    if active_sign is not None:
        headline = "SIGN: %s" % active_sign
        headline_color = LABEL_COLORS.get(active_sign, WHITE)
    else:
        headline = "SIGN: --  (SAFE STATE)"
        headline_color = SAFE_COLOR
    _draw_text(image, headline, (10, max(20, int(bar_height * 0.42))),
               headline_color, 0.62, 1)

    if detection is not None and detection.confidence < threshold:
        detail = "candidate %s %.2f < %.2f -> SAFE" % (
            detection.label, detection.confidence, threshold)
    elif safe:
        detail = "no sign / confidence below threshold (%s)" % (reason or "-")
    else:
        detail = "confidence %.2f | status: %s" % (
            detection.confidence if detection else 0.0, reason or "-")
    _draw_text(image, detail, (10, max(40, int(bar_height * 0.78))),
               WHITE, 0.44, 1)

    led_states = led_states or {}
    marker_x = width - 150
    marker_y = max(18, int(bar_height * 0.40))
    for index, color_name in enumerate(("red", "yellow", "green")):
        center = (marker_x + index * 45, marker_y)
        on = led_states.get(color_name, 0)
        fill = LED_COLORS[color_name] if on else (60, 60, 60)
        cv2.circle(image, center, 10, fill, -1)
        cv2.circle(image, center, 10, WHITE, 1)
        cv2.putText(image, color_name[0].upper(),
                    (center[0] - 4, center[1] + 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, WHITE, 1, cv2.LINE_AA)

    footer = "FPS %.1f | threshold %.2f" % (fps, threshold)
    _filled_bar(image, (0, height - 24), (width, height), (20, 20, 20), 0.65)
    _draw_text(image, footer, (10, height - 8), WHITE, 0.42, 1)

    return image
