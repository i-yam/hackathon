"""Erzeugt fertige Beispiel-INPUT-PDFs aus dem 1.OG-Ausfuehrungsplan zum Hochladen in der UI:

  beispiel_inputs/plan_raum_ausschnitt.pdf   - Ausschnitt mit einem/wenigen Raeumen (Plan-Input)
  beispiel_inputs/legende.pdf                 - die Legende (Material-Schluessel)
  beispiel_inputs/schnitt.pdf                 - der Schnitt (Deckenaufbau)

So kann man Plan + Legende + Schnitt getrennt als PDF in die UI geben.
    python examples/generate_beispiel_inputs.py
"""
from __future__ import annotations

import io
from pathlib import Path

import fitz
from PIL import Image

HERE = Path(__file__).resolve().parent
REAL = HERE / "real_plans"
OUT = HERE / "beispiel_inputs"
OUT.mkdir(exist_ok=True)
DPI = 300
MAX_EDGE = 3500  # laengste Kante begrenzen -> kompakte Dateien


def clip_to_pdf(src_pdf: Path, bbox_frac, ziel: Path, page_no: int = 0):
    """Schneidet einen Anteils-Ausschnitt aus und speichert ihn JPEG-komprimiert als PDF (klein)."""
    doc = fitz.open(src_pdf)
    page = doc[page_no]
    r = page.rect
    x0, y0, x1, y1 = bbox_frac
    clip = fitz.Rect(r.x0 + r.width * x0, r.y0 + r.height * y0,
                     r.x0 + r.width * x1, r.y0 + r.height * y1)
    pix = page.get_pixmap(matrix=fitz.Matrix(DPI / 72, DPI / 72), clip=clip)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    if max(img.size) > MAX_EDGE:  # herunterskalieren falls zu gross
        f = MAX_EDGE / max(img.size)
        img = img.resize((int(img.width * f), int(img.height * f)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    out_doc = fitz.open()
    pg = out_doc.new_page(width=img.width, height=img.height)
    pg.insert_image(fitz.Rect(0, 0, img.width, img.height), stream=buf.getvalue())
    out_doc.save(ziel, deflate=True)
    print(f"  {ziel.name}: {img.width}x{img.height}px, {ziel.stat().st_size//1024} KB")


def main():
    plan = next(REAL.glob("*1.OBERGESCHOSS*.pdf"))
    schnitt = next(REAL.glob("*SCHNITT*.pdf"))

    # 1) Raum-Ausschnitt (linke obere Wohnung mit einigen Raeumen)
    clip_to_pdf(plan, (0.05, 0.08, 0.34, 0.46), OUT / "plan_raum_ausschnitt.pdf")
    # 2) Legende (rechter Bereich)
    clip_to_pdf(plan, (0.78, 0.16, 1.00, 0.82), OUT / "legende.pdf")
    # 3) Schnitt (ganze Seite; bei Bedarf in der UI separat hochladbar)
    clip_to_pdf(schnitt, (0.0, 0.0, 1.0, 1.0), OUT / "schnitt.pdf")
    print("fertig ->", OUT)


if __name__ == "__main__":
    main()
