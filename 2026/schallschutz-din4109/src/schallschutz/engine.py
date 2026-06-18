"""Deterministische DIN-4109-Berechnungsengine (Stufe 2).

Reine Physik/Norm-Logik, kein LLM. Alle Formeln mit Quellenangabe.

  m'            flaechenbezogene Masse           DIN 4109-32, Gl.(3):  m' = d * rho
  R_w           bew. Schalldaemm-Mass massiv     DIN 4109-32, Gl.(13)-(16) je Material
  R'_w          bau-/eingebauter Wert            DIN 4109-2: R'w = R_w + dRw(Vorsatz) - K (Flanken)
  L_n,eq,0,w    aequiv. Norm-Trittschallpegel    DIN 4109-32, Gl.(21): 164 - 35*lg(m')
  L'_n,w        bau-/eingebauter Trittschall     DIN 4109-2, Gl.(22): L_n,eq,0,w - dLw + K
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .knowledge import resolve_material
from .models import Bauteil, Bauteiltyp, Schicht

# Massekurven-Kategorien mit eigener R_w(m')-Gleichung (DIN 4109-32, 4.1.4.2)
_CURVE_CATS = {"beton", "ks", "ziegel", "verfuellstein", "leichtbeton", "porenbeton"}

# Luftschall-Flankenkorrektur: vereinfachte Standardannahme (R'w = R_w - K).
# Exakt waere das EN-12354-4-Wege-Modell (Dd/Ff/Fd/Df) nach DIN 4109-2, 4.2.2 (Ausbaustufe).
K_FLANKE_LUFT_DEFAULT = 2.0   # dB
# Trittschall: mittlere flaechenbezogene Masse der flankierenden Bauteile m'_f,m (Default).
# Wird in nachweis.py aus den Massivwaenden des Modells abgeleitet, falls vorhanden.
M_FLANK_MITTEL_DEFAULT = 300.0  # kg/m2


def k_trittschall_flanke(m_s: float, m_f_m: float) -> tuple[float, str]:
    """Korrekturwert K fuer Trittschall-Flankenuebertragung, uebereinanderliegende Raeume.

    DIN 4109-2:2018, 4.3.2.1.1, Gl.(26)/(27) — Massivdecke ohne Unterdecke.
    Gueltig: 100 <= m'_s <= 900, 100 <= m'_f,m <= 500.
    """
    if m_f_m <= m_s:
        k = 0.6 + 5.5 * math.log10(m_s / m_f_m)
        return round(k, 1), "K = 0,6 + 5,5*lg(m's/m'f,m)  [DIN 4109-2 Gl.(26)]"
    return 0.0, "K = 0 dB (m'f,m > m's)  [DIN 4109-2 Gl.(27)]"


# Standard-Trittschallverbesserung schwimmender Zementestrich auf Trittschalldaemmung
# (DIN 4109-34; konservativer Richtwert, im Modell pro Bauteil ueberschreibbar via delta_lw)
DELTA_LW_SCHWIMMESTRICH_DEFAULT = 27.0


@dataclass
class SchichtErgebnis:
    material: str
    erkannt_als: Optional[str]
    dicke_mm: float
    rohdichte: Optional[float]
    masse_kg_m2: Optional[float]
    kategorie: Optional[str]
    in_masse: bool = True   # False = schwimmender Boden, zaehlt nicht zur Rohdecken-Masse
    warnung: Optional[str] = None


@dataclass
class BauteilErgebnis:
    bauteil_id: str
    typ: str
    schichten: list[SchichtErgebnis] = field(default_factory=list)
    masse_kg_m2: Optional[float] = None
    massekurve: Optional[str] = None
    rw_massiv: Optional[float] = None        # R_w der Massivkonstruktion
    rw_konstruktion: Optional[float] = None  # inkl. Vorsatzschale dRw
    rw_strich: Optional[float] = None        # R'w eingebaut (mit Flankenkorrektur)
    ln_eq_0_w: Optional[float] = None        # aequiv. Norm-Trittschallpegel Rohdecke
    lnw_strich: Optional[float] = None       # L'n,w eingebaut
    # fuer den transparenten Rechengang exponierte Eingangswerte
    dlw_verwendet: Optional[float] = None     # tatsaechlich angesetztes dLw
    k_luft: Optional[float] = None
    k_tritt: Optional[float] = None           # berechnete Trittschall-Flankenkorrektur K (Gl.26/27)
    m_flank_mittel: Optional[float] = None     # m'_f,m der flankierenden Bauteile
    schwimmender_estrich: bool = False
    hinweise: list[str] = field(default_factory=list)
    formeln: list[str] = field(default_factory=list)


def _ist_estrich(key: Optional[str], material: str) -> bool:
    name = (key or material or "").lower()
    return "estrich" in name


def _schwimmender_boden_indizes(details: list[SchichtErgebnis]) -> set[int]:
    """Erkennt einen schwimmenden Estrich: Estrich-Schicht, die an eine Daemmschicht grenzt.

    Diese Schichten zaehlen nach DIN 4109-32, 4.8.4.2 NICHT zur Rohdecken-Masse; ihre
    Trittschallwirkung wird ueber dLw (DIN 4109-34) erfasst.
    """
    aus: set[int] = set()
    for i, s in enumerate(details):
        if s.kategorie == "daemmung":
            nachbarn = [j for j in (i - 1, i + 1) if 0 <= j < len(details)]
            if any(_ist_estrich(details[j].erkannt_als, details[j].material) for j in nachbarn):
                aus.add(i)
                for j in nachbarn:
                    if _ist_estrich(details[j].erkannt_als, details[j].material):
                        aus.add(j)
    return aus


def analysiere_schichten(
    schichten: list[Schicht], decke: bool
) -> tuple[Optional[float], list[SchichtErgebnis], Optional[str], bool]:
    """Liefert (Rohbau-Masse m', Schicht-Details, massgebende Massekurve, schwimmender_boden?).

    Bei Decken wird ein erkannter schwimmender Estrich aus der Masse herausgerechnet.
    Massgebende Massekurve = Kategorie der massereichsten Kurven-Schicht (Beton/KS/Ziegel/...).
    """
    details: list[SchichtErgebnis] = []
    for s in schichten:
        key, mat = resolve_material(s.material)
        if mat is None:
            details.append(SchichtErgebnis(s.material, None, s.dicke_mm, None, None, None,
                                           warnung=f"Material '{s.material}' nicht im Katalog gefunden"))
            continue
        rho = s.rohdichte_override if s.rohdichte_override else mat["rohdichte"]
        masse = (s.dicke_mm / 1000.0) * rho
        details.append(SchichtErgebnis(s.material, key, s.dicke_mm, rho, round(masse, 1), mat["kategorie"]))

    schwimmend = False
    if decke:
        aus = _schwimmender_boden_indizes(details)
        for i in aus:
            details[i].in_masse = False
        schwimmend = bool(aus)

    total = 0.0
    curve_mass: dict[str, float] = {}
    for s in details:
        if s.masse_kg_m2 is None or not s.in_masse:
            continue
        total += s.masse_kg_m2
        if s.kategorie in _CURVE_CATS:
            curve_mass[s.kategorie] = curve_mass.get(s.kategorie, 0.0) + s.masse_kg_m2
    if total == 0:
        return None, details, None, schwimmend
    massekurve = max(curve_mass, key=curve_mass.get) if curve_mass else None
    return round(total, 1), details, massekurve, schwimmend


def rw_aus_masse(m: float, kategorie: str) -> tuple[float, str]:
    """Bewertetes Schalldaemm-Mass R_w einschalig massiv (DIN 4109-32, Gl.13-16)."""
    if kategorie in ("beton", "ks", "ziegel", "verfuellstein"):
        rw = 30.9 * math.log10(m) - 22.2
        return rw, "R_w = 30,9*lg(m') - 22,2  [DIN 4109-32 Gl.(13)]"
    if kategorie == "leichtbeton":
        rw = 30.9 * math.log10(m) - 20.2
        return rw, "R_w = 30,9*lg(m') - 20,2  [DIN 4109-32 Gl.(14)]"
    if kategorie == "porenbeton":
        if m < 150:
            rw = 32.6 * math.log10(m) - 22.5
            return rw, "R_w = 32,6*lg(m') - 22,5  [DIN 4109-32 Gl.(15)]"
        rw = 26.1 * math.log10(m) - 8.4
        return rw, "R_w = 26,1*lg(m') - 8,4  [DIN 4109-32 Gl.(16)]"
    raise ValueError(f"Keine Massekurve fuer Kategorie '{kategorie}'")


def masse_fuer_rw(rw_ziel: float, kategorie: str) -> Optional[float]:
    """Inverse von rw_aus_masse: welche flaechenbez. Masse m' erreicht ein Ziel-R_w?"""
    if kategorie in ("beton", "ks", "ziegel", "verfuellstein"):
        return 10 ** ((rw_ziel + 22.2) / 30.9)
    if kategorie == "leichtbeton":
        return 10 ** ((rw_ziel + 20.2) / 30.9)
    if kategorie == "porenbeton":
        m = 10 ** ((rw_ziel + 22.5) / 32.6)
        return m if m < 150 else 10 ** ((rw_ziel + 8.4) / 26.1)
    return None


def gueltigkeit_hinweis(m: float, kategorie: str) -> Optional[str]:
    grenzen = {
        "beton": (65, 720), "ks": (65, 720), "ziegel": (65, 720), "verfuellstein": (65, 720),
        "leichtbeton": (140, 480), "porenbeton": (50, 300),
    }
    lo, hi = grenzen.get(kategorie, (None, None))
    if lo is None:
        return None
    if m < lo or m > hi:
        return f"m' = {m:.0f} kg/m2 liegt ausserhalb des Gueltigkeitsbereichs ({lo}..{hi} kg/m2) der Massekurve '{kategorie}'"
    return None


def ln_eq_0_w(m: float) -> tuple[float, str]:
    """Aequivalenter bewerteter Norm-Trittschallpegel der Rohdecke (DIN 4109-32, Gl.21)."""
    val = 164.0 - 35.0 * math.log10(m)
    return val, "L_n,eq,0,w = 164 - 35*lg(m')  [DIN 4109-32 Gl.(21), gueltig 100..720 kg/m2]"


def berechne_bauteil(
    bt: Bauteil,
    k_flanke_luft: float = K_FLANKE_LUFT_DEFAULT,
    m_flank_mittel: float = M_FLANK_MITTEL_DEFAULT,
) -> BauteilErgebnis:
    """Vollstaendige akustische Berechnung eines Bauteils aus seinem Aufbau."""
    erg = BauteilErgebnis(bauteil_id=bt.id, typ=bt.typ.value)
    erg.k_luft = k_flanke_luft
    erg.m_flank_mittel = m_flank_mittel

    # Tueren/Fenster: kein Massivaufbau -> direkter Rw-Wert (R_w, nur ueber das Element)
    if bt.typ in (Bauteiltyp.TUER, Bauteiltyp.FENSTER):
        if bt.rw_element is not None:
            erg.rw_konstruktion = round(bt.rw_element, 1)
            erg.rw_strich = round(bt.rw_element, 1)  # Tueranforderung gilt fuer Rw direkt
            erg.hinweise.append("Tuer/Fenster: Anforderung gilt fuer R_w (nur ueber das Element); kein Flankenabzug.")
        else:
            erg.hinweise.append("Kein R_w-Wert fuer Tuer/Fenster angegeben (Datenblatt erforderlich).")
        return erg

    # Massivbauteile: Masse -> R_w -> R'w (+ ggf. Trittschall)
    ist_decke = bt.typ == Bauteiltyp.DECKE
    m, details, massekurve, schwimmend = analysiere_schichten(bt.schichten, ist_decke)
    erg.schichten = details
    erg.masse_kg_m2 = m
    erg.massekurve = massekurve
    erg.schwimmender_estrich = schwimmend
    if schwimmend:
        erg.hinweise.append("Schwimmender Estrich erkannt: Masse nicht in Rohdecke angesetzt "
                            "(DIN 4109-32, 4.8.4.2); Wirkung ueber dLw.")

    if bt.rw_element is not None:
        # explizit vorgegebener Elementwert (z.B. aus Zulassung) hat Vorrang
        erg.rw_massiv = round(bt.rw_element, 1)
        erg.formeln.append("R_w direkt vorgegeben (Zulassung/Pruefzeugnis)")
    elif m is not None and massekurve is not None:
        rw, formel = rw_aus_masse(m, massekurve)
        erg.rw_massiv = round(rw, 1)
        erg.formeln.append(f"m' = {m:.0f} kg/m2")
        erg.formeln.append(formel)
        warn = gueltigkeit_hinweis(m, massekurve)
        if warn:
            erg.hinweise.append(warn)
    else:
        erg.hinweise.append("R_w nicht bestimmbar: keine Massivschicht mit Massekurve und kein direkter R_w-Wert.")
        return erg

    # Vorsatzschale (DIN 4109-34)
    erg.rw_konstruktion = round(erg.rw_massiv + bt.delta_rw_vorsatz, 1)
    if bt.delta_rw_vorsatz:
        erg.formeln.append(f"+ dRw(Vorsatz) = {bt.delta_rw_vorsatz:+.1f} dB  [DIN 4109-34]")

    # eingebauter Wert R'w mit vereinfachter Flankenkorrektur (DIN 4109-2)
    erg.rw_strich = round(erg.rw_konstruktion - k_flanke_luft, 1)
    erg.formeln.append(f"R'w = R_w(Konstr.) - K_Flanke({k_flanke_luft:.1f} dB)  [DIN 4109-2, vereinfacht]")

    # Trittschall nur fuer Decken
    if ist_decke and m is not None:
        ln0, tformel = ln_eq_0_w(m)
        erg.ln_eq_0_w = round(ln0, 1)
        erg.formeln.append(tformel)
        if m < 100 or m > 720:
            erg.hinweise.append(f"Trittschall: m' = {m:.0f} kg/m2 ausserhalb 100..720 kg/m2 (Gl.21).")
        # dLw: explizit vorgegeben, sonst Standardwert falls schwimmender Estrich erkannt
        dlw = bt.delta_lw
        if dlw == 0 and schwimmend:
            dlw = DELTA_LW_SCHWIMMESTRICH_DEFAULT
            erg.hinweise.append(f"dLw = {dlw:.0f} dB (Standardwert schwimmender Zementestrich, DIN 4109-34) angesetzt.")
        erg.dlw_verwendet = dlw
        # Flankenkorrektur K nach DIN 4109-2 Gl.(26/27) aus Decken- und mittlerer Flankenmasse
        k_t, kformel = k_trittschall_flanke(m, m_flank_mittel)
        erg.k_tritt = k_t
        if not (100 <= m_flank_mittel <= 500):
            erg.hinweise.append(f"m'f,m = {m_flank_mittel:.0f} kg/m2 ausserhalb 100..500 (Gl.26 Gueltigkeit).")
        lnw = ln0 - dlw + k_t
        erg.lnw_strich = round(lnw, 1)
        erg.formeln.append(kformel + f"  -> K = {k_t:+.1f} dB (m's={m:.0f}, m'f,m={m_flank_mittel:.0f})")
        erg.formeln.append(f"L'n,w = L_n,eq,0,w - dLw({dlw:.1f}) + K({k_t:+.1f})  [DIN 4109-2 Gl.(25)]")
        if dlw == 0:
            erg.hinweise.append("dLw = 0: kein schwimmender Estrich/Bodenbelag angesetzt (Rohdecke).")

    return erg
