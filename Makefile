PYTHON ?= python3

.PHONY: help run headless simulate live live-sim test signs dataset demo diagrams benchmark leds

help:
	@echo "Targets:"
	@echo "  run        Jalankan sistem (kamera + GPIO + display bila ada)"
	@echo "  headless   Jalankan tanpa jendela OpenCV"
	@echo "  simulate   Jalankan headless + GPIO simulasi"
	@echo "  live       Live camera: jendela + stream web (port 8000)"
	@echo "  live-sim   Live camera tanpa jendela + GPIO simulasi"
	@echo "  test       Unit test"
	@echo "  demo       Generate video demo STOP-SLOW-GO"
	@echo "  benchmark  Synthetic benchmark"
	@echo "  leds       Tes 3 LED (simulasi)"

run:
	$(PYTHON) main.py

headless:
	$(PYTHON) main.py --headless

simulate:
	$(PYTHON) main.py --headless --simulate-gpio

live:
	$(PYTHON) tools/live_camera.py

live-sim:
	$(PYTHON) tools/live_camera.py --no-window --simulate-gpio

test:
	$(PYTHON) -m unittest discover -s tests -v

demo:
	$(PYTHON) tools/make_demo_video.py

diagrams:
	$(PYTHON) tools/make_diagrams.py

benchmark:
	$(PYTHON) tools/synthetic_benchmark.py

leds:
	$(PYTHON) tools/test_leds.py --simulate
