"""Legenden-bewusste Kachel-Extraktion fuer echte Ausfuehrungsplaene (dichte A1-Plaene 1:50).

Anders als der einfache Einzelbild-Extraktor (claude_vision.py) bewaeltigt dieses Modul
grosse, dichte Plaene, deren Beschriftung beim Herunterskalieren des Gesamtbilds unlesbar wuerde:

  1. extract_legend()  - liest die Legende (Schraffur -> Material, Fussbodenaufbauten)
  2. extract_tile()     - je hochaufgeloeste Plan-Kachel: Raeume + Waende + WHG (Nutzungseinheiten)
  3. extract_section()  - liest den Schnitt: Decken-/Estrichaufbau
  4. merge_*           - dedupliziert und baut das Projekt-Modell

Jede Funktion macht genau einen Claude-Vision-Call (SDK + Max-Abo). Ergebnis ist ein
best-effort-Modell, das im Streamlit-HITL-Editor geprueft/korrigiert wird.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import fitz

from ..knowledge import materials, requirements
from ..models import Bauteil, Gebaeude, Gebaeudetyp, Nutzungseinheit, Projekt, Raum, Schicht
from .claude_vision import _extract_json, _query_claude


def _frage(prompt: str) -> str:
    """Synchroner Wrapper um den async SDK-Call."""
    return asyncio.run(_query_claude(prompt))

# Standard-Bildausschnitte (Anteile der Seitenbreite/-hoehe) — fuer typische A1-Plaene,
# im Aufruf ueberschreibbar. Legende/Schriftfeld liegen rechts.
DEFAULT_PLAN_BBOX = (0.02, 0.05, 0.78, 0.95)
DEFAULT_LEGEND_BBOX = (0.78, 0.16, 1.00, 0.82)


def _mat_keys() -> str:
    return ", ".join(materials().keys())


def _wand_rollen() -> str:
    return ", ".join(k for k, v in requirements().items() if v["bauteil"] == "wand")


# --------------------------------------------------------------------------- Rendering
def render_clip(pdf_path, page_no: int, bbox_frac, dpi: int, out: Path) -> Path:
    """Rendert einen rechteckigen Ausschnitt (Anteils-BBox) einer PDF-Seite als PNG."""
    doc = fitz.open(pdf_path)
    page = doc[page_no]
    r = page.rect
    x0, y0, x1, y1 = bbox_frac
    clip = fitz.Rect(r.x0 + r.width * x0, r.y0 + r.height * y0,
                     r.x0 + r.width * x1, r.y0 + r.height * y1)
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), clip=clip)
    out.parent.mkdir(parents=True, exist_ok=True)
    pix.save(out)
    return out


def plan_kacheln(pdf_path, page_no: int, plan_bbox, grid: tuple[int, int],
                 overlap: float, dpi: int, out_dir: Path) -> list[tuple[Path, tuple]]:
    """Zerlegt die Plan-BBox in ueberlappende Kacheln; liefert (Pfad, Region-bbox_frac)."""
    x0, y0, x1, y1 = plan_bbox
    nx, ny = grid
    w, h = (x1 - x0) / nx, (y1 - y0) / ny
    out = []
    for j in range(ny):
        for i in range(nx):
            bx0 = max(x0, x0 + i * w - overlap * w)
            by0 = max(y0, y0 + j * h - overlap * h)
            bx1 = min(x1, x0 + (i + 1) * w + overlap * w)
            by1 = min(y1, y0 + (j + 1) * h + overlap * h)
            p = render_clip(pdf_path, page_no, (bx0, by0, bx1, by1), dpi,
                            out_dir / f"kachel_{j+1}_{i+1}.png")
            out.append((p, (bx0, by0, bx1, by1)))
    return out


def _bbox_tile_to_plan(bbox, region, plan_bbox):
    """Wand-bbox (relativ zur Kachel) -> relativ zum Vollplan-Vorschaubild (plan_bbox-Region)."""
    if not bbox or len(bbox) != 4:
        return None
    rx0, ry0, rx1, ry1 = region
    px0, py0, px1, py1 = plan_bbox
    pw, ph = (px1 - px0), (py1 - py0)
    if pw <= 0 or ph <= 0:
        return None
    clamp = lambda v: max(0.0, min(1.0, v))
    return [
        clamp((rx0 + bbox[0] * (rx1 - rx0) - px0) / pw),
        clamp((ry0 + bbox[1] * (ry1 - ry0) - py0) / ph),
        clamp((rx0 + bbox[2] * (rx1 - rx0) - px0) / pw),
        clamp((ry0 + bbox[3] * (ry1 - ry0) - py0) / ph),
    ]


# --------------------------------------------------------------------------- Legende
def extract_legend(legend_img: Path) -> dict:
    prompt = f"""Lies die Bilddatei {legend_img.resolve()} mit dem Read-Tool.
Es ist die LEGENDE eines Architektur-Ausfuehrungsplans.

Extrahiere als JSON:
1. "wand_materialien": je Schraffur/Eintrag der Mauerwerks-/Bauteil-Legende ein Objekt
   {{"bedeutung": "<Text der Legende>", "material_key": "<einer aus der Liste>"}}.
2. "fussbodenaufbauten": je Fussbodenaufbau (z.B. 'Fussbodenaufbau Wohnung')
   {{"name": "<Name>", "schichten": [{{"material":"<key>","dicke_mm":<zahl>}}, ...]}}.
   Estrich + Trittschalldaemmung als getrennte Schichten.

ERLAUBTE material_key: {_mat_keys()}
Nur was lesbar ist. Antworte mit GENAU EINEM JSON-Objekt in einem ```json ... ``` Block."""
    return _extract_json(_frage(prompt))


# --------------------------------------------------------------------------- Kachel
def extract_tile(tile_img: Path, legend_hint: str) -> dict:
    prompt = f"""Lies die Bilddatei {tile_img.resolve()} mit dem Read-Tool.
Es ist ein AUSSCHNITT eines Grundriss-Ausfuehrungsplans (Mehrfamilienhaus, M 1:50).

Arbeite RAUM-ZENTRISCH: Gehe die Raeume in diesem Ausschnitt durch und erfasse je Raum seine Waende.
Extrahiere NUR was in DIESEM Ausschnitt klar lesbar ist, als JSON:
1. "raeume": [{{"nummer":"<z.B. 1.1.06>","name":"<z.B. Wohnen>","nutzung":"<wohnraum/schlafraum/bad/kueche/flur/treppenraum>",
   "whg":"<Wohnungs-/Nutzungseinheit, z.B. WHG6 - falls erkennbar>","flaeche_m2":<Grundflaeche, sonst null>}}]
2. "waende": [{{"raum_a":"<Raum-Nr ODER Name, zu dem diese Wand gehoert>",
   "raum_b":"<angrenzender Raum-Nr/Name; null wenn AUSSENWAND>",
   "material":"<material_key>","dicke_mm":<zahl aus z.B. 'h=20cm' -> 200>,
   "laenge_m":<Wandlaenge oder null>,"hoehe_m":<Raumhoehe oder null>,"fenster_flaeche_m2":<oder null>,
   "bbox":[<x0>,<y0>,<x1>,<y1>],
   "din_rolle":"<nur fuer Trennbauteile einer aus: {_wand_rollen()} - sonst null>","brandschutz":"<z.B. F90 - oder null>"}}]
   bbox = ungefaehre Lage der Wand IN DIESEM AUSSCHNITT, relativ 0..1 (0/0 oben links, 1/1 unten rechts).
3. "tueren": [{{"bezeichnung":"<z.B. T30 RS>","brandschutz":"<T30/...>","fuehrt_zu":"<kurz>"}}]

raum_a/raum_b mit den Raum-Nummern/Namen aus 1. referenzieren. Material aus Schraffur/Beschriftung.
Legenden-Hinweis (Schraffur->Material): {legend_hint}
Wandstaerke meist als 'h=..cm' oder am Bemassungsstrich. Betonguete 'C25/30' bedeutet Stahlbeton.
Keine Werte erfinden (null statt raten). Antworte mit GENAU EINEM JSON-Objekt in ```json ... ```."""
    return _extract_json(_frage(prompt))


# --------------------------------------------------------------------------- Schnitt
def extract_section(section_img: Path) -> dict:
    prompt = f"""Lies die Bilddatei {section_img.resolve()} mit dem Read-Tool.
Es ist ein SCHNITT eines Mehrfamilienhauses (M 1:50).

Extrahiere den typischen Geschossdecken-/Wohnungstrenndecken-Aufbau als JSON:
{{"trenndecke": {{"rohdecke_material":"<material_key>","rohdecke_dicke_mm":<zahl>,
  "fussbodenaufbau":[{{"material":"<key>","dicke_mm":<zahl>}}, ...]}}}}
Rohdecke = tragende Stahlbetondecke. Fussbodenaufbau = Estrich + Trittschalldaemmung darueber.
ERLAUBTE material_key: {_mat_keys()}
Nur lesbare Werte (sonst null). Antworte mit GENAU EINEM JSON-Objekt in ```json ... ```."""
    return _extract_json(_frage(prompt))


# --------------------------------------------------------------------------- Merge
_PUTZ = {"material": "gipsputz", "dicke_mm": 15}


def _wand_schichten(material: str, dicke_mm: float) -> list[dict]:
    """Wandaufbau: Kernmaterial + beidseitig Putz (Standardannahme, im HITL editierbar)."""
    kern = {"material": material or "stahlbeton", "dicke_mm": dicke_mm or 175}
    return [dict(_PUTZ), kern, dict(_PUTZ)]


def _norm(s) -> str:
    return str(s).strip().lower().replace(".", "_").replace(" ", "_") if s else ""


def merge_to_projekt(legend: dict, tiles: list[dict], section: dict | None,
                     quelle: str, plan_bbox=DEFAULT_PLAN_BBOX) -> tuple[Projekt, dict]:
    """Fuehrt Legende + Kachel-Extrakte (+ Schnitt) zu einem deduplizierten Projekt zusammen.

    Waende werden raum-zentrisch zugeordnet (raum_a/raum_b -> Raum-IDs), damit der
    Raum->Wand-Flow auch bei echten Plaenen greift. Faellt auf altes Format (trennt) zurueck.
    """
    raeume: dict[str, Raum] = {}
    whg_map: dict[str, set[str]] = {}
    ref2rid: dict[str, str] = {}   # normalisierte Raum-Nr/Name -> rid
    rid2whg: dict[str, str] = {}
    wand_seen: set[tuple] = set()
    bauteile: list[Bauteil] = []
    wand_idx = 0

    def resolve(ref):
        return ref2rid.get(_norm(ref)) if ref else None

    for t in tiles:
        for rd in t.get("raeume", []) or []:
            num = (rd.get("nummer") or rd.get("name") or "").strip()
            if not num:
                continue
            rid = "r_" + _norm(num)
            whg = (rd.get("whg") or "").strip() or None
            whg_id = ("whg_" + whg.replace(" ", "").lower()) if whg else None
            if rid not in raeume:
                raeume[rid] = Raum(
                    id=rid, name=rd.get("name") or num,
                    nutzung=(rd.get("nutzung") or "aufenthaltsraum"),
                    nutzungseinheit=whg_id, flaeche_m2=rd.get("flaeche_m2"),
                )
            else:
                ex = raeume[rid]
                if ex.flaeche_m2 is None and rd.get("flaeche_m2") is not None:
                    ex.flaeche_m2 = rd["flaeche_m2"]
                if ex.nutzungseinheit is None and whg_id:
                    ex.nutzungseinheit = whg_id
            # Referenzen (Nummer + Name) auf rid abbilden
            for ref in (rd.get("nummer"), rd.get("name")):
                if ref:
                    ref2rid[_norm(ref)] = rid
            if whg_id:
                whg_map.setdefault(whg_id, set()).add(rid)
                rid2whg[rid] = whg_id

        region = t.get("_region")
        for wd in t.get("waende", []) or []:
            # Raumzuordnung: neues Format (raum_a/raum_b) bevorzugt, sonst altes (trennt_einheiten)
            hat_refs = "raum_a" in wd or "raum_b" in wd
            if not hat_refs and not wd.get("trennt_einheiten"):
                continue
            rid_a = resolve(wd.get("raum_a"))
            rid_b = resolve(wd.get("raum_b"))
            rolle = wd.get("din_rolle") or None
            versch = bool(rolle) or (rid_a and rid_b and rid2whg.get(rid_a) != rid2whg.get(rid_b))
            if hat_refs and not rid_a and not rid_b and not rolle:
                versch = False  # reine Innenwand ohne Zuordnung -> trotzdem aufnehmen
            mat = wd.get("material") or "stahlbeton"
            dk = wd.get("dicke_mm") or 175
            sig = (rid_a, rid_b, rolle, mat, round(float(dk) / 10) * 10)
            if sig in wand_seen:
                continue
            wand_seen.add(sig)
            wand_idx += 1
            bbox_plan = _bbox_tile_to_plan(wd.get("bbox"), region, plan_bbox) if region else None
            bauteile.append(Bauteil(
                id=f"W-{wand_idx:02d}", typ="wand", din_rolle=rolle,
                raum_a=rid_a, raum_b=rid_b, verschiedene_einheiten=bool(versch),
                laenge_m=wd.get("laenge_m"), hoehe_m=wd.get("hoehe_m"),
                fenster_flaeche_m2=wd.get("fenster_flaeche_m2"), bbox=bbox_plan,
                schichten=[Schicht(**s) for s in _wand_schichten(mat, float(dk))],
                bemerkung=(f"{wd.get('raum_a') or ''}↔{wd.get('raum_b') or 'außen'}"
                           f"{' / ' + wd['brandschutz'] if wd.get('brandschutz') else ''}").strip("/ "),
            ))

    # Nutzungseinheiten
    einheiten = [Nutzungseinheit(id=k, name=k.replace("whg_", "WHG ").upper(), raeume=sorted(v))
                 for k, v in whg_map.items()]

    # Wohnungstrenndecke je Wohnung. Bodenaufbau-Fallback: Schnitt -> Legende -> leer (HITL).
    td = (section or {}).get("trenndecke") or {}
    roh_mat = td.get("rohdecke_material") or "stahlbeton"
    roh_d = td.get("rohdecke_dicke_mm") or 200
    boden = td.get("fussbodenaufbau") or []
    boden_quelle = "Schnitt"
    if not boden:
        lboeden = legend.get("fussbodenaufbauten") or []
        if lboeden and lboeden[0].get("schichten"):
            boden = lboeden[0]["schichten"]
            boden_quelle = "Legende"
    # nur vollstaendige Schichten (Material + Dicke vorhanden)
    boden = [s for s in boden if s.get("material") and s.get("dicke_mm")]
    decke_hinweis = ""
    if not boden:
        boden_quelle = "fehlt"
        decke_hinweis = " — Fussbodenaufbau (Estrich) NICHT extrahiert, bitte ergaenzen (dLw)"

    def _mk(s):
        return Schicht(material=s["material"], dicke_mm=float(s["dicke_mm"]),
                       rohdichte_override=s.get("rohdichte_override"))
    schichten = [_mk(s) for s in boden] + [Schicht(material=roh_mat or "stahlbeton", dicke_mm=float(roh_d or 200))]
    decke_idx = 0
    for eh in (einheiten or [None]):
        decke_idx += 1
        raum_a = eh.raeume[0] if (eh and eh.raeume) else None  # Decke einem Raum der Wohnung zuordnen
        bauteile.append(Bauteil(
            id=f"D-{decke_idx:02d}", typ="decke", din_rolle="wohnungstrenndecke",
            raum_a=raum_a, verschiedene_einheiten=True,
            schichten=[Schicht(**s.model_dump()) for s in schichten],
            bemerkung=f"Wohnungstrenndecke (Rohdecke {roh_mat} {roh_d:.0f}mm, Boden: {boden_quelle})"
                      f"{' fuer ' + eh.name if eh else ''}{decke_hinweis}",
        ))

    projekt = Projekt(
        name="Schallschutznachweis (Ausfuehrungsplan)",
        quelle_plan=quelle,
        gebaeude=Gebaeude(typ=Gebaeudetyp.MEHRFAMILIENHAUS),
        nutzungseinheiten=einheiten,
        raeume=list(raeume.values()),
        bauteile=bauteile,
    )
    roh = {"legende": legend, "kacheln": tiles, "schnitt": section}
    return projekt, roh


# --------------------------------------------------------------------------- Orchestrator
def extrahiere_real_plan(
    pdf_path, page_no: int = 0, *, grid: tuple[int, int] = (2, 2), overlap: float = 0.08,
    dpi: int = 300, plan_bbox=DEFAULT_PLAN_BBOX, legend_bbox=DEFAULT_LEGEND_BBOX,
    schnitt_pdf=None, legend_image=None, arbeitsordner="outputs/_real_pages", progress=None,
) -> tuple[Projekt, dict, list[Path]]:
    """Komplette Extraktion eines echten Ausfuehrungsplans -> Projekt.

    progress: optionaler Callback(str) fuer Status (z.B. Streamlit).
    """
    pdf_path = Path(pdf_path)
    work = Path(arbeitsordner)
    work.mkdir(parents=True, exist_ok=True)

    def say(m):
        if progress:
            progress(m)

    say("Legende rendern & lesen …")
    if legend_image:  # separat hochgeladene Legende (Bild oder PDF) bevorzugen
        legend_image = Path(legend_image)
        if legend_image.suffix.lower() == ".pdf":
            legend_img = render_clip(legend_image, 0, (0.0, 0.0, 1.0, 1.0), dpi, work / "legende.png")
        else:
            legend_img = legend_image
    else:
        legend_img = render_clip(pdf_path, page_no, legend_bbox, dpi, work / "legende.png")
    try:
        legend = extract_legend(legend_img)
    except Exception as e:
        legend = {"_fehler": str(e)}
    legend_hint = "; ".join(
        f"{w.get('bedeutung','?')} -> {w.get('material_key','?')}"
        for w in legend.get("wand_materialien", [])
    )[:600] or "keine Legende gelesen"

    say(f"Plan in {grid[0]}x{grid[1]} Kacheln zerlegen …")
    kacheln = plan_kacheln(pdf_path, page_no, plan_bbox, grid, overlap, dpi, work)
    tiles = []
    for n, (kpath, region) in enumerate(kacheln, 1):
        say(f"Kachel {n}/{len(kacheln)} extrahieren …")
        try:
            t = extract_tile(kpath, legend_hint)
        except Exception as e:
            t = {"_fehler": str(e)}
        t["_region"] = list(region)  # Kachel-Region fuer bbox-Transformation merken
        tiles.append(t)

    section = None
    if schnitt_pdf:
        say("Schnitt lesen (Deckenaufbau) …")
        sec_img = render_clip(schnitt_pdf, 0, (0.0, 0.0, 1.0, 1.0), max(dpi, 250), work / "schnitt.png")
        try:
            section = extract_section(sec_img)
        except Exception as e:
            section = {"_fehler": str(e)}

    # Vollplan-Vorschaubild (Plan-Region) fuer das Wand-Overlay — moderate Auflösung
    say("Vorschaubild rendern …")
    plan_preview = render_clip(pdf_path, page_no, plan_bbox, min(dpi, 120), work / "plan_preview.png")

    say("Zusammenfuehren …")
    projekt, roh = merge_to_projekt(legend, tiles, section, pdf_path.name, plan_bbox=plan_bbox)
    images = [plan_preview, legend_img] + [k for k, _ in kacheln]
    return projekt, roh, images
