
#!/usr/bin/env python3
"""GPIO LED Controller for NVIDIA Jetson Nano."""

try:
    import Jetson.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO = None
    GPIO_AVAILABLE = False


class LedController:
    def __init__(
        self,
        pins,
        sign_colors,
        active_high=True,
        mode="BOARD",
        safe_state="all_off",
        blink_hz=2.0,
        simulate=False,
        logger=None,
    ):
        self.pins = {
            color.lower(): int(pin)
            for color, pin in pins.items()
        }
        self.sign_colors = {
            str(sign).strip().upper(): str(color).strip().lower()
            for sign, color in sign_colors.items()
        }

        self.active_high = bool(active_high)
        self.mode = str(mode).upper()
        self.safe_state = safe_state
        self.blink_hz = blink_hz
        self.simulate = simulate or not GPIO_AVAILABLE
        self.logger = logger or print

        self.current_state = {
            color: 0 for color in self.pins
        }

        if len(set(self.pins.values())) != len(self.pins):
            raise ValueError("Setiap LED harus menggunakan pin GPIO berbeda.")

        if self.mode not in ("BOARD", "BCM"):
            raise ValueError("Mode GPIO harus BOARD atau BCM.")

        if not self.simulate:
            GPIO.setwarnings(False)
            GPIO.setmode(
                GPIO.BOARD if self.mode == "BOARD" else GPIO.BCM
            )

            off_level = GPIO.LOW if self.active_high else GPIO.HIGH

            for pin in self.pins.values():
                GPIO.setup(pin, GPIO.OUT, initial=off_level)

        self.all_off()
        self.logger(
            "LedController siap (simulasi: %s, active_high: %s)"
            % (self.simulate, self.active_high)
        )

    def _write_pin(self, color, on):
        if self.simulate:
            return

        if self.active_high:
            level = GPIO.HIGH if on else GPIO.LOW
        else:
            level = GPIO.LOW if on else GPIO.HIGH

        GPIO.output(self.pins[color], level)

    def all_off(self):
        """Matikan seluruh LED."""
        for color in self.pins:
            self._write_pin(color, False)
            self.current_state[color] = 0

        return dict(self.current_state)

    def apply(self, sign_label, now=None):
        """Nyalakan tepat satu LED sesuai sign; sign invalid = semua mati."""
        sign = (
            str(sign_label).strip().upper()
            if sign_label is not None
            else ""
        )
        target_color = self.sign_colors.get(sign)

        if target_color not in self.pins:
            self.all_off()
            self.logger("Sign tidak valid: %r -> semua LED OFF" % sign_label)
            return dict(self.current_state)

        # Matikan semuanya terlebih dahulu agar tidak ada LED tertinggal ON.
        self.all_off()

        # Nyalakan hanya LED yang sesuai dengan sign.
        self._write_pin(target_color, True)
        self.current_state[target_color] = 1

        self.logger(
            "%s -> %s ON; LED lainnya OFF"
            % (sign, target_color.upper())
        )
        return dict(self.current_state)

    def close(self):
        """Matikan LED dan lepaskan pin yang digunakan."""
        try:
            self.all_off()
        finally:
            if not self.simulate:
                GPIO.cleanup(list(self.pins.values()))

        self.logger("GPIO dibersihkan.")



