"""LED output through Jetson.GPIO (with a simulation backend for testing)."""

import time


class LedController(object):
    """Control one LED per sign colour.

    pins        : dict colour -> physical BOARD pin (e.g. {"red": 7, ...})
    sign_colors : dict sign label -> colour (e.g. {"STOP": "red", ...})
    safe_state  : "all_off" or "blink_yellow"
    """

    def __init__(self, pins, sign_colors, active_high=True, mode="BOARD",
                 safe_state="all_off", blink_hz=2.0, simulate=False,
                 logger=None):
        self.pins = dict(pins)
        self.sign_colors = dict(sign_colors)
        self.active_high = bool(active_high)
        self.mode = mode
        self.safe_state = safe_state
        self.blink_hz = float(blink_hz)
        self.simulate = bool(simulate)
        self.log = logger or (lambda message: None)

        self._gpio = None
        self._closed = False
        self.states = dict((color, 0) for color in self.pins)
        self._last_blink_phase = None

        if not self.simulate:
            self._setup_gpio()
        else:
            self.log("GPIO simulation mode enabled")

    # ------------------------------------------------------------------
    def _setup_gpio(self):
        try:
            import Jetson.GPIO as GPIO
        except ImportError:
            raise RuntimeError(
                "Jetson.GPIO tidak tersedia. Gunakan --simulate-gpio atau "
                "instal paket python3-jetson-gpio.")

        self._gpio = GPIO
        GPIO.setwarnings(False)
        mode = GPIO.BOARD if str(self.mode).upper() == "BOARD" else GPIO.BCM
        GPIO.setmode(mode)
        for color, pin in self.pins.items():
            GPIO.setup(pin, GPIO.OUT)
            self._write_pin(pin, 0)
        self.log("GPIO ready (mode=%s, pins=%s)" % (self.mode, self.pins))

    def _write_pin(self, pin, on):
        if self.simulate:
            return
        level = 1 if on else 0
        if not self.active_high:
            level = 0 if level else 1
        self._gpio.output(pin, level)

    def _write_color(self, color, on):
        on = 1 if on else 0
        if self.states.get(color, 0) == on:
            return
        self.states[color] = on
        self._write_pin(self.pins[color], on)

    # ------------------------------------------------------------------
    def apply(self, sign, now=None):
        """Set the LEDs according to the active sign (None means safe)."""
        if now is None:
            now = time.time()

        desired = dict((color, 0) for color in self.pins)

        if sign is not None and sign in self.sign_colors:
            color = self.sign_colors[sign]
            if color in desired:
                desired[color] = 1
        elif self.safe_state == "blink_yellow" and "yellow" in desired:
            half_period = 0.5 / max(0.1, self.blink_hz)
            phase = int(now / half_period) % 2
            desired["yellow"] = 1 if phase == 0 else 0

        for color, value in desired.items():
            self._write_color(color, value)
        return dict(self.states)

    def all_off(self):
        for color in self.pins:
            self._write_color(color, 0)
        return dict(self.states)

    def status_text(self):
        return "R=%d Y=%d G=%d" % (
            self.states.get("red", 0),
            self.states.get("yellow", 0),
            self.states.get("green", 0),
        )

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.all_off()
        finally:
            if self._gpio is not None:
                try:
                    self._gpio.cleanup(list(self.pins.values()))
                except Exception:
                    try:
                        self._gpio.cleanup()
                    except Exception:
                        pass
        self.log("GPIO cleaned up")
