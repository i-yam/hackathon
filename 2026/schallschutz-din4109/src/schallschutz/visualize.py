"""Plan-Overlay: erkannte Waende (bbox) auf das Planbild zeichnen + Auswahl markieren."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .knowledge import requirement_for, resolve_material
from .models import Bauteil

_FARBE = "#1f6feb"        # erkannt
_FARBE_HL = "#cf222e"     # markiert/ausgewählt
_FARBE_DECKE = "#1a7f37"  # Decke


def _font(size: int):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def wand_label(b: Bauteil, raum_namen: dict | None = None) -> str:
    """Ordentlicher, sprechender Name statt '—'."""
    raum_namen = raum_namen or {}
    # Rolle / Art
    if b.din_rolle:
        req = requirement_for(b.din_rolle)
        art = req["bezeichnung"].split("(")[0].strip() if req else b.din_rolle.replace("_", " ")
    elif b.typ.value == "decke":
        art = "Decke"
    elif b.typ.value == "tuer":
        art = "Tür"
    elif b.typ.value == "fenster":
        art = "Fenster"
    elif b.raum_b is None:
        art = "Außenwand"
    else:
        nb = raum_namen.get(b.raum_b, b.raum_b)
        art = f"Innenwand (zu {nb})" if nb else "Innenwand"
    # Material + Dicke
    matinfo = ""
    if b.rw_element is not None:
        matinfo = f"Rw {b.rw_element:.0f} dB"
    elif b.schichten:
        kern = None
        for s in b.schichten:
            key, mat = resolve_material(s.material)
            if mat and mat["kategorie"] not in ("schicht", "daemmung"):
                kern = (key or s.material, s.dicke_mm)
                break
        if kern is None:
            kern = (b.schichten[len(b.schichten) // 2].material, b.schichten[len(b.schichten) // 2].dicke_mm)
        matinfo = f"{kern[0]} {kern[1]/10:.1f} cm"
    fenster = " · Fenster" if b.fenster_flaeche_m2 else ""
    teile = [b.id, art] + ([matinfo] if matinfo else [])
    return " · ".join(teile) + fenster


def zeichne_wand_overlay(image_path, bauteile: list[Bauteil], highlight_id: str | None = None):
    """Zeichnet alle Bauteile mit bbox auf das Planbild; markiert highlight_id rot."""
    img = Image.open(image_path).convert("RGB")
    d = ImageDraw.Draw(img, "RGBA")
    W, H = img.size
    f = _font(max(14, W // 90))
    for b in bauteile:
        if not b.bbox or len(b.bbox) != 4:
            continue
        x0, y0, x1, y1 = b.bbox
        px = [x0 * W, y0 * H, x1 * W, y1 * H]
        px = [min(px[0], px[2]), min(px[1], px[3]), max(px[0], px[2]), max(px[1], px[3])]
        sel = (b.id == highlight_id)
        col = _FARBE_HL if sel else (_FARBE_DECKE if b.typ.value == "decke" else _FARBE)
        width = max(4, W // 250) if sel else max(2, W // 500)
        if sel:  # halbtransparente Füllung für die Auswahl
            d.rectangle(px, fill=(207, 34, 46, 60), outline=col, width=width)
        else:
            d.rectangle(px, outline=col, width=width)
        # Label-Plakette
        tx, ty = px[0], max(0, px[1] - f.size - 4)
        try:
            tb = d.textbbox((tx, ty), b.id, font=f)
            d.rectangle(tb, fill=col)
        except Exception:
            pass
        d.text((tx, ty), b.id, fill="white", font=f)
    return img
