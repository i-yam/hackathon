"""Erzeugt einen synthetischen Architektur-Grundriss (PNG + PDF) als Demo-Input fuer die Extraktion.

Zwei Wohnungen, getrennt durch eine schraffierte Wohnungstrennwand (Label 'KS 17,5'),
mit Raumbeschriftung, Bemassung, Fenster- und Tuersymbolen.
    python examples/generate_synthetic_plan.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1800, 1150
SCALE = 90  # px pro Meter (Annaeherung)
OUT = Path(__file__).resolve().parent


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def hatch(d, box, step=12, color="#555"):
    x0, y0, x1, y1 = box
    d.rectangle(box, outline="black", width=2)
    x = x0 - (y1 - y0)
    while x < x1:
        d.line([(max(x, x0), y0 if x >= x0 else y0 + (x0 - x)),
                (min(x + (y1 - y0), x1), y1 if x + (y1 - y0) <= x1 else y1 - (x + (y1 - y0) - x1))],
               fill=color, width=1)
        x += step


def dim(d, p1, p2, text, f, vertical=False):
    d.line([p1, p2], fill="#1f6feb", width=1)
    for p in (p1, p2):
        if vertical:
            d.line([(p[0] - 6, p[1]), (p[0] + 6, p[1])], fill="#1f6feb", width=1)
        else:
            d.line([(p[0], p[1] - 6), (p[0], p[1] + 6)], fill="#1f6feb", width=1)
    mx, my = (p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2
    d.text((mx + (8 if vertical else -20), my + (-8 if not vertical else -8)), text, fill="#1f6feb", font=f)


def main():
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f = _font(26)
    fs = _font(20)
    fb = _font(34)

    d.text((40, 30), "GRUNDRISS Obergeschoss 1  —  M 1:100", fill="black", font=fb)

    ox, oy = 120, 140
    wall = 18  # Aussenwanddicke px

    # Aussenkontur
    outer = (ox, oy, ox + 15 * SCALE, oy + 9 * SCALE)
    d.rectangle(outer, outline="black", width=wall // 2)

    midx = ox + 7.5 * SCALE
    # Wohnungstrennwand (mittig, dick, schraffiert)
    tw = (midx - 9, oy, midx + 9, oy + 9 * SCALE)
    hatch(d, tw, step=10)
    d.text((midx - 60, oy + 9 * SCALE + 12), "KS 17,5", fill="black", font=f)
    d.text((midx + 18, oy + 4.2 * SCALE), "Wohnungs-\ntrennwand", fill="#333", font=fs)

    # ---- Wohnung 1 (links): Schlafzimmer + Wohnzimmer ----
    d.text((ox + 40, oy + 10), "WOHNUNG 1", fill="#888", font=fs)
    # Innenwand horizontal
    iny = oy + 4 * SCALE
    d.line([(ox, iny), (midx - 9, iny)], fill="black", width=8)

    d.text((ox + 1.2 * SCALE, oy + 1.6 * SCALE), "Schlafzimmer", fill="black", font=f)
    d.text((ox + 1.9 * SCALE, oy + 1.6 * SCALE + 30), "14.2 m²", fill="black", font=f)
    d.text((ox + 1.5 * SCALE, oy + 5.4 * SCALE), "Wohnzimmer", fill="black", font=f)
    d.text((ox + 2.0 * SCALE, oy + 5.4 * SCALE + 30), "24.0 m²", fill="black", font=f)

    # ---- Wohnung 2 (rechts): Schlafzimmer ----
    d.text((midx + 1.2 * SCALE, oy + 10), "WOHNUNG 2", fill="#888", font=fs)
    d.text((midx + 2.2 * SCALE, oy + 4.0 * SCALE), "Schlafzimmer", fill="black", font=f)
    d.text((midx + 2.9 * SCALE, oy + 4.0 * SCALE + 30), "20.5 m²", fill="black", font=f)

    # Fenster (Aussenwand) als doppelte Linie
    for (fx0, fx1, fy) in [(ox + 1.5 * SCALE, ox + 3.5 * SCALE, oy)]:
        d.rectangle([fx0, fy - 6, fx1, fy + 6], fill="white", outline="#1f6feb", width=3)
        d.text(((fx0 + fx1) / 2 - 35, fy - 34), "Fenster", fill="#1f6feb", font=fs)
    for fy0, fy1 in [(oy + 1.2 * SCALE, oy + 3.0 * SCALE)]:
        fx = ox + 15 * SCALE
        d.rectangle([fx - 6, fy0, fx + 6, fy1], fill="white", outline="#1f6feb", width=3)
        d.text((fx + 12, (fy0 + fy1) / 2), "Fenster", fill="#1f6feb", font=fs)

    # Tuer (Treppenraum -> Wohnung 1) als Boegen
    door_y = oy + 4 * SCALE
    d.arc([ox - 4, door_y - 50, ox + 90, door_y + 40], start=270, end=360, fill="#aa3a00", width=3)
    d.text((ox - 110, door_y - 10), "Tür\nRw=37", fill="#aa3a00", font=fs)

    # Bemassung
    dim(d, (ox, oy - 40), (midx - 9, oy - 40), "7.50 m", fs)
    dim(d, (midx + 9, oy - 40), (ox + 15 * SCALE, oy - 40), "7.50 m", fs)
    dim(d, (ox - 50, oy), (ox - 50, oy + 9 * SCALE), "9.00 m", fs, vertical=True)

    # Legende
    ly = oy + 9 * SCALE + 70
    d.text((40, ly), "Legende:  ▥ Kalksandstein (KS)   ▦ Stahlbetondecke (Schnitt)   "
                     "Decke OG1/OG2: Stahlbeton 20 cm + schwimmender Estrich",
           fill="#333", font=fs)

    png = OUT / "plan_demo.png"
    pdf = OUT / "plan_demo.pdf"
    img.save(png)
    img.save(pdf, "PDF", resolution=150)
    print("geschrieben:", png, "und", pdf)


if __name__ == "__main__":
    main()
