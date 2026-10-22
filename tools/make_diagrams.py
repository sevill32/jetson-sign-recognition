#!/usr/bin/env python3
"""Generate the architecture and wiring diagrams in docs/."""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")

ARCH_DOT = r"""
digraph SignRecognition {
  rankdir=TB;
  graph [fontname="Helvetica", fontsize=11, bgcolor="white",
         nodesep=0.45, ranksep=0.38, pad=0.25];
  node [shape=box, style="rounded,filled", fontname="Helvetica",
        fontsize=11, color="#4a4a4a", fillcolor="#f5f7fa", penwidth=1.1];
  edge [fontname="Helvetica", fontsize=10, color="#4a4a4a", penwidth=1.1];

  subgraph cluster_input {
    label="Input"; fontsize=12; color="#8aa4c8"; style="rounded";
    camera [label="Kamera CSI IMX219\n(atau webcam USB)", fillcolor="#e8f1fb"];
    capture [label="Frame Capture\nGStreamer/Argus -> appsink",
             fillcolor="#e8f1fb"];
  }

  subgraph cluster_cv {
    label="Computer Vision"; fontsize=12; color="#8ac89a"; style="rounded";
    cv [label="Sign Detection\nresize + blur + HSV color mask\ncontour + convex hull + approxPolyDP\nshape & color scoring",
        fillcolor="#eaf7ee"];
    conf [label="Confidence\n0.55 shape + 0.30 color + 0.15 area",
          fillcolor="#eaf7ee"];
  }

  subgraph cluster_logic {
    label="Decision Logic"; fontsize=12; color="#d8b978"; style="rounded";
    decision [label="Threshold + Debounce\nconfidence >= 0.55, stabil 5 frame,\nhilang 8 frame",
              fillcolor="#fff6df"];
    safe [label="Safe State\nsemua LED OFF\n(atau kuning blink)",
          fillcolor="#fff6df"];
  }

  subgraph cluster_output {
    label="Output"; fontsize=12; color="#c88a8a"; style="rounded";
    gpio [label="Jetson.GPIO\nBOARD pin 7 / 11 / 13", fillcolor="#fdeaea"];
    led [label="LED\nMERAH / KUNING / HIJAU", fillcolor="#fdeaea"];
    ui [label="Overlay + Log\nsign, confidence, status LED,\nCSV + snapshot",
        fillcolor="#fdeaea"];
  }

  camera -> capture -> cv -> conf -> decision;
  decision -> gpio [label="STOP / SLOW / GO"];
  gpio -> led;
  decision -> safe [style=dashed,
                    label="tidak ada sign / < threshold"];
  safe -> gpio [style=dashed];
  decision -> ui;
  safe -> ui;
}
"""


def generate_architecture():
    os.makedirs(DOCS, exist_ok=True)
    dot_path = os.path.join(DOCS, "architecture.dot")
    with open(dot_path, "w") as handle:
        handle.write(ARCH_DOT)
    for fmt in ("png", "svg"):
        out = os.path.join(DOCS, "architecture.%s" % fmt)
        command = ["dot", "-T%s" % fmt, "-Gdpi=150", dot_path, "-o", out]
        subprocess.check_call(command)
        print("OK %s" % out)


def generate_wiring():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle

    fig, ax = plt.subplots(figsize=(13, 7.6))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title("Diagram Wiring - Jetson Nano + 3 LED (BOARD numbering)",
                 fontsize=15, fontweight="bold", y=1.015)

    board = FancyBboxPatch((0.35, 0.65), 3.45, 6.55,
                           boxstyle="round,pad=0.02,rounding_size=0.08",
                           facecolor="#2f6b4f", edgecolor="#173d2c",
                           linewidth=2)
    ax.add_patch(board)
    ax.text(2.08, 6.85, "JETSON NANO", color="white", ha="center",
            fontsize=13, fontweight="bold")
    ax.text(2.08, 6.55, "40-pin header", color="#cfe8db", ha="center",
            fontsize=9)

    pins = [
        ("Pin 7", "GPIO09 / BCM 4", 5.65),
        ("Pin 11", "GPIO17 / BCM 17", 4.85),
        ("Pin 13", "GPIO27 / BCM 27", 4.05),
        ("Pin 6", "GND", 2.25),
    ]
    pin_x = 3.80
    for name, gpio, y in pins:
        ax.plot([pin_x, pin_x + 0.12], [y, y], color="#cccccc", lw=3)
        ax.add_patch(Rectangle((pin_x - 0.30, y - 0.15), 0.30, 0.30,
                               facecolor="#f5d76e", edgecolor="#7a6a20",
                               lw=1, zorder=5))
        ax.text(pin_x - 0.42, y + 0.10, name, ha="right", va="center",
                color="white", fontsize=9, fontweight="bold")
        ax.text(pin_x - 0.42, y - 0.10, gpio, ha="right", va="center",
                color="#cfe8db", fontsize=7.5)

    gnd_bus_x = 9.55
    gnd_y = 2.25
    ax.plot([gnd_bus_x, gnd_bus_x], [4.05, gnd_y], color="#444444",
            lw=2, zorder=1)
    ax.plot([pin_x + 0.12, gnd_bus_x], [gnd_y, gnd_y], color="#444444",
            lw=2, zorder=1)
    ax.add_patch(Circle((gnd_bus_x, gnd_y), 0.06, color="#444444",
                        zorder=6))

    row_y = {"red": 5.65, "yellow": 4.85, "green": 4.05}
    led_color = {"red": "#e74c3c", "yellow": "#f1c40f", "green": "#2ecc71"}
    led_letter = {"red": "R", "yellow": "Y", "green": "G"}

    for color, y in row_y.items():
        ax.plot([pin_x + 0.12, 5.05], [y, y], color="#333333", lw=2)
        ax.add_patch(Rectangle((5.05, y - 0.16), 1.15, 0.32,
                               facecolor="#e6d8a8", edgecolor="#7a6a20",
                               lw=1.2, zorder=4))
        ax.text(5.62, y + 0.30, "330 Ohm", ha="center", fontsize=8.5,
                color="#4a4a4a")

        ax.plot([6.20, 7.30], [y, y], color="#333333", lw=2)
        ax.add_patch(Polygon([[7.30, y - 0.28], [7.30, y + 0.28],
                              [8.00, y]], closed=True,
                             facecolor=led_color[color], edgecolor="#333333",
                             lw=1.2, zorder=5))
        ax.text(7.52, y, led_letter[color], ha="center", va="center",
                color="white", fontsize=9, fontweight="bold", zorder=7)
        ax.plot([8.00, 8.00], [y - 0.32, y + 0.32], color="#333333", lw=2.5,
                zorder=6)
        ax.plot([8.00, gnd_bus_x], [y, y], color="#333333", lw=2)
        ax.add_patch(Circle((gnd_bus_x, y), 0.055, color="#444444", zorder=6))

        arrow_x = 7.50
        for offset in (0.0, 0.18):
            ax.annotate("", xy=(arrow_x + 0.48 + offset, y + 0.58 + offset),
                        xytext=(arrow_x + 0.22 + offset, y + 0.34 + offset),
                        arrowprops=dict(arrowstyle="->", color=led_color[color],
                                        lw=1.1))

    ax.text(2.05, 3.15,
            "Pin 6 (GND) -> rel GND\nSemua katoda LED ke GND",
            ha="center", fontsize=8.5, color="white",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#1f4d38",
                      edgecolor="#cfe8db"))

    notes = (
        "Catatan:\n"
        "- Gunakan resistor 220-330 Ohm pada setiap LED.\n"
        "- Anoda LED -> resistor -> pin GPIO; katoda -> GND (pin 6).\n"
        "- GPIO Jetson Nano = 3.3 V, arus kecil. Jangan menyalakan LED\n"
        "  tanpa resistor.\n"
        "- Cabut daya sebelum melakukan wiring.\n"
        "- Verifikasi pin header carrier board masing-masing."
    )
    ax.text(10.05, 6.95, notes, fontsize=8.2, va="top", color="#333333",
            bbox=dict(boxstyle="round,pad=0.45", facecolor="#f5f7fa",
                      edgecolor="#b8c4d4"))

    mapping = (
        "Mapping output:\n"
        "STOP  -> LED MERAH  (pin 7)\n"
        "SLOW  -> LED KUNING (pin 11)\n"
        "GO    -> LED HIJAU  (pin 13)\n"
        "SAFE  -> semua LED OFF"
    )
    ax.text(10.05, 4.95, mapping, fontsize=8.8, va="top", color="#333333",
            bbox=dict(boxstyle="round,pad=0.45", facecolor="#fff6df",
                      edgecolor="#d8b978"))

    ax.text(6.5, 0.25,
            "Alur: Camera -> Sign Recognition -> Decision Logic -> GPIO -> LED",
            ha="center", fontsize=8.8, color="#444444")

    fig.tight_layout()
    for fmt in ("png", "svg"):
        out = os.path.join(DOCS, "wiring.%s" % fmt)
        fig.savefig(out, dpi=200, bbox_inches="tight",
                    facecolor="white")
        print("OK %s" % out)
    plt.close(fig)


def main():
    generate_architecture()
    generate_wiring()
    return 0


if __name__ == "__main__":
    sys.exit(main())
