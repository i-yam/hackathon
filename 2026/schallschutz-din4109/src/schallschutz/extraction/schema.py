"""Prompt + erlaubte Werte fuer die Vision-Extraktion (Stufe 1).

Die erlaubten DIN-Rollen und Material-Aliase werden aus der Wissensbasis abgeleitet,
damit Claude kanonische Schluessel liefert, die die Engine direkt versteht.
"""
from __future__ import annotations

import json

from ..knowledge import materials, requirements


def _erlaubte_rollen() -> str:
    lines = []
    for key, r in requirements().items():
        lines.append(f"  - {key}  ({r['bauteil']}, {r['bezeichnung']})")
    return "\n".join(lines)


def _erlaubte_materialien() -> str:
    lines = []
    for key, m in materials().items():
        aliases = ", ".join(m.get("aliases", [])[:4])
        lines.append(f"  - {key}  (rho={m['rohdichte']} kg/m3; erkennbar als: {aliases})")
    return "\n".join(lines)


_BEISPIEL = {
    "name": "Schallschutznachweis <Bauvorhaben>",
    "bauvorhaben": "<Adresse falls erkennbar>",
    "quelle_plan": "<Dateiname>",
    "gebaeude": {"typ": "mehrfamilienhaus", "geschosse": 3, "erhoehter_schallschutz": False},
    "raeume": [
        {"id": "r1", "name": "Schlafzimmer", "nutzung": "schlafraum",
         "nutzungseinheit": "whg1", "geschoss": "OG1",
         "flaeche_m2": 14.2, "laenge_m": 4.2, "breite_m": 3.38, "hoehe_m": 2.5}
    ],
    "bauteile": [
        {"id": "BT-01", "typ": "wand", "din_rolle": "wohnungstrennwand",
         "raum_a": "r1", "raum_b": "r2", "verschiedene_einheiten": True,
         "bbox": [0.30, 0.10, 0.34, 0.62],
         "laenge_m": 4.2, "hoehe_m": 2.5, "fenster_flaeche_m2": None, "flaeche_m2": 10.5,
         "schichten": [
             {"material": "gipsputz", "dicke_mm": 15},
             {"material": "kalksandstein_1.8", "dicke_mm": 175, "rohdichte_override": None},
             {"material": "gipsputz", "dicke_mm": 15}
         ],
         "delta_rw_vorsatz": 0.0, "delta_lw": 0.0,
         "bemerkung": "Schraffur Diagonal + Label 'KS 17,5'"},
        {"id": "BT-02", "typ": "wand", "din_rolle": None,
         "raum_a": "r1", "raum_b": None, "verschiedene_einheiten": False,
         "laenge_m": 3.4, "hoehe_m": 2.5, "fenster_flaeche_m2": 2.1,
         "schichten": [{"material": "stahlbeton", "dicke_mm": 200}],
         "bemerkung": "Aussenwand mit Fenster (raum_b=null bedeutet aussen)"},
        {"id": "BT-05", "typ": "tuer", "din_rolle": "tuer_aufenthaltsraum",
         "raum_a": "treppenraum", "raum_b": "r1", "rw_element": 37.0,
         "bemerkung": "Wohnungseingangstuer"}
    ]
}


def build_extraction_prompt(image_paths: list[str], quelle: str) -> str:
    reads = "\n".join(f"  - {p}" for p in image_paths)
    schema = json.dumps(_BEISPIEL, ensure_ascii=False, indent=2)
    return f"""Du bist ein Bauingenieur-Assistent fuer Schallschutznachweise nach DIN 4109.
Lies die folgende(n) Bilddatei(en) eines Architektur-Grundrisses/Schnitts mit dem Read-Tool:
{reads}

AUFGABE: Extrahiere ALLE schallschutzrelevanten Informationen und gib sie als EIN JSON-Objekt zurueck,
das exakt dem unten gezeigten Schema entspricht.

Arbeite RAUM-ZENTRISCH: Gehe jeden Raum durch und erfasse dazu ALLE seine Begrenzungswaende.

Erkenne und extrahiere:
1. RAUMGEOMETRIE: Raumname, Nutzung, Abmessungen (Laenge/Breite/Hoehe in m), Flaeche, Geschoss,
   Zuordnung zu einer Wohnung/Nutzungseinheit.
2. BAUTEILE - pro Raum ALLE umschliessenden Waende (nicht nur Trennbauteile!), plus Decken/Tueren/Fenster:
   - raum_a = der betrachtete Raum, raum_b = angrenzender Raum (oder null, wenn AUSSENWAND).
   - verschiedene_einheiten=true nur wenn das Bauteil FREMDE Nutzungseinheiten/Treppenraum trennt.
   - WANDGEOMETRIE: laenge_m (Wandlaenge), hoehe_m (Raumhoehe), fenster_flaeche_m2 (Fenster in der Wand, sonst null).
   - bbox: ungefaehre Lage der Wand IM BILD als [x0,y0,x1,y1] RELATIV (0..1, 0/0 = oben links, 1/1 = unten rechts).
3. MATERIAL + AUFBAU aus Schraffuren/Symbolen/Beschriftungen: je Schicht Material und Dicke (mm).
   Bsp.: Diagonalschraffur + 'KS 17,5' -> Kalksandstein 175 mm; 'Stb 20'/'C25/30' -> Stahlbeton 200 mm.
   Beidseitigen Putz als eigene Schichten ergaenzen, falls ueblich/erkennbar (~15 mm Gipsputz).
4. DIN-ROLLE: nur fuer Trennbauteile eine Rolle aus der Liste setzen; sonstige Waende din_rolle=null.
5. Bei Tueren/Fenstern statt Schichten ein 'rw_element' (dB) setzen, falls erkennbar, sonst weglassen.

ERLAUBTE din_rolle-WERTE (nutze exakt diese Schluessel):
{_erlaubte_rollen()}

ERLAUBTE material-WERTE (nutze diese Schluessel; bei abweichender Dichte 'rohdichte_override' setzen):
{_erlaubte_materialien()}

WICHTIG:
- Wenn ein Wert nicht aus dem Plan ablesbar ist: Feld weglassen oder null. NICHTS erfinden.
- Masse/dB NICHT selbst berechnen - nur Geometrie, Material, Dicke, Rolle liefern. Die Berechnung macht die Engine.
- quelle_plan = "{quelle}".
- Antworte mit GENAU EINEM JSON-Objekt in einem ```json ... ``` Codeblock, ohne weiteren Text.

SCHEMA (Beispielstruktur):
```json
{schema}
```"""
