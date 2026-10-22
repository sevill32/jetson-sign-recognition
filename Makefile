PYTHON ?= python3

.PHONY: help run headless simulate test signs demo diagrams benchmark leds

help:
	@echo "Targets:"
	@echo "  run        Jalankan sistem (kamera + GPIO + display bila ada)"
	@echo "  headless   Jalankan tanpa jendela OpenCV"
	@echo "  simulate   Jalankan headless + GPIO simulasi"
	@echo "  test       Unit test"
	@echo "  signs      Generate gambar sign untuk dicetak"
	@echo "  demo       Generate video demo STOP-SLOW-GO"
	@echo "  diagrams   Generate diagram arsitektur + wiring"
	@echo "  benchmark  Synthetic benchmark"
	@echo "  leds       Tes 3 LED (simulasi)"

run:
	$(PYTHON) main.py

headless:
	$(PYTHON) main.py --headless

simulate:
	$(PYTHON) main.py --headless --simulate-gpio

test:
	$(PYTHON) -m unittest discover -s tests -v

signs:
	$(PYTHON) tools/make_signs.py

demo:
	$(PYTHON) tools/make_demo_video.py

diagrams:
	$(PYTHON) tools/make_diagrams.py

benchmark:
	$(PYTHON) tools/synthetic_benchmark.py

leds:
	$(PYTHON) tools/test_leds.py --simulate
