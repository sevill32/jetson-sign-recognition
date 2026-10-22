"""Decision logic: confidence threshold, debounce and fail-safe state."""


class DecisionResult(object):
    __slots__ = ("sign", "confidence", "safe", "changed", "reason",
                 "candidate")

    def __init__(self, sign, confidence, safe, changed, reason, candidate):
        self.sign = sign
        self.confidence = float(confidence)
        self.safe = bool(safe)
        self.changed = bool(changed)
        self.reason = reason
        self.candidate = candidate

    def __repr__(self):
        return "DecisionResult(sign=%s, conf=%.3f, safe=%s, reason=%s)" % (
            self.sign, self.confidence, self.safe, self.reason)


class DecisionLogic(object):
    """Turn per-frame detections into a stable sign / safe-state decision.

    A sign must be seen for `stable_frames` consecutive frames before it is
    accepted. When no valid sign is seen for `missing_frames` consecutive
    frames, the system returns to the safe state.
    """

    def __init__(self, threshold=0.55, stable_frames=5, missing_frames=8):
        self.threshold = float(threshold)
        self.stable_frames = max(1, int(stable_frames))
        self.missing_frames = max(1, int(missing_frames))

        self.active_sign = None
        self.candidate = None
        self.candidate_count = 0
        self.missing_count = 0
        self.last_confidence = 0.0
        self.last_reason = "startup"

    def reset(self):
        self.active_sign = None
        self.candidate = None
        self.candidate_count = 0
        self.missing_count = 0
        self.last_confidence = 0.0
        self.last_reason = "reset"

    def update(self, detection):
        """Feed one Detection (or None) and return a DecisionResult."""
        changed = False
        reason = self.last_reason

        if detection is not None and detection.confidence >= self.threshold:
            self.missing_count = 0
            self.last_confidence = detection.confidence

            if detection.label == self.candidate:
                self.candidate_count += 1
            else:
                self.candidate = detection.label
                self.candidate_count = 1

            if (self.candidate_count >= self.stable_frames and
                    self.active_sign != self.candidate):
                self.active_sign = self.candidate
                changed = True
                reason = "sign_stable"
            elif self.active_sign == self.candidate:
                reason = "sign_hold"
            else:
                reason = "stabilizing"
        else:
            if detection is None:
                reason = "no_sign"
            else:
                reason = "low_confidence"
                self.last_confidence = detection.confidence

            self.candidate = None
            self.candidate_count = 0
            self.missing_count += 1

            if (self.active_sign is not None and
                    self.missing_count >= self.missing_frames):
                self.active_sign = None
                changed = True
                reason = "missing_sign"

        self.last_reason = reason
        confidence = detection.confidence if detection is not None else 0.0

        return DecisionResult(
            sign=self.active_sign,
            confidence=confidence,
            safe=self.active_sign is None,
            changed=changed,
            reason=reason,
            candidate=detection,
        )
