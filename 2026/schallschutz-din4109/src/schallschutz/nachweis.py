"""Nachweisfuehrung: vorhandene Werte (engine) gegen DIN-4109-1 Anforderungen pruefen."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .engine import BauteilErgebnis, M_FLANK_MITTEL_DEFAULT, analysiere_schichten, berechne_bauteil
from .knowledge import requirement_for
from .models import Bauteiltyp, Projekt


@dataclass
class NachweisZeile:
    bauteil_id: str
    typ: str
    din_rolle: Optional[str]
    bezeichnung: str
    tabelle_zeile: str
    # Luftschall
    erf_rw: Optional[float]
    vorh_rw: Optional[float]
    rw_ok: Optional[bool]
    # Trittschall
    zul_lnw: Optional[float]
    vorh_lnw: Optional[float]
    lnw_ok: Optional[bool]
    status: str  # "gruen" | "rot" | "offen"
    ergebnis: BauteilErgebnis
    hinweise: list[str] = field(default_factory=list)


@dataclass
class NachweisErgebnis:
    projekt: Projekt
    zeilen: list[NachweisZeile] = field(default_factory=list)
    gesamt_status: str = "offen"

    @property
    def anzahl_ok(self) -> int:
        return sum(1 for z in self.zeilen if z.status == "gruen")

    @property
    def anzahl_rot(self) -> int:
        return sum(1 for z in self.zeilen if z.status == "rot")

    @property
    def anzahl_offen(self) -> int:
        return sum(1 for z in self.zeilen if z.status == "offen")


def mittlere_flankenmasse(projekt: Projekt) -> float:
    """m'_f,m: Mittelwert der flaechenbez. Masse der massiven Waende im Modell (DIN 4109-2)."""
    massen = []
    for bt in projekt.bauteile:
        if bt.typ == Bauteiltyp.WAND and bt.schichten:
            m, _, _, _ = analysiere_schichten(bt.schichten, decke=False)
            if m:
                massen.append(m)
    if not massen:
        return M_FLANK_MITTEL_DEFAULT
    return round(sum(massen) / len(massen), 1)


def _pruefe_bauteil(bt, k_luft, m_flank) -> NachweisZeile:
    erg = berechne_bauteil(bt, k_flanke_luft=k_luft, m_flank_mittel=m_flank)
    req = requirement_for(bt.din_rolle) if bt.din_rolle else None

    erf_rw = req.get("erf_Rw") if req else None
    zul_lnw = req.get("zul_Lnw") if req else None
    bezeichnung = req.get("bezeichnung") if req else "(keine DIN-Rolle zugeordnet)"
    tz = f"Tab.{req['tabelle']} Z.{req['zeile']}" if req else "-"

    vorh_rw = erg.rw_strich
    vorh_lnw = erg.lnw_strich

    rw_ok = None
    if erf_rw is not None and vorh_rw is not None:
        rw_ok = vorh_rw >= erf_rw
    lnw_ok = None
    if zul_lnw is not None and vorh_lnw is not None:
        lnw_ok = vorh_lnw <= zul_lnw

    # Statusableitung: rot wenn eine geforderte Pruefung fehlschlaegt,
    # offen wenn eine geforderte Groesse nicht berechenbar war, sonst gruen.
    checks = [c for c in (rw_ok, lnw_ok) if c is not None]
    fehlend = (erf_rw is not None and vorh_rw is None) or (zul_lnw is not None and vorh_lnw is None)
    if req is None:
        status = "offen"
    elif fehlend:
        status = "offen"
    elif checks and all(checks):
        status = "gruen"
    elif any(c is False for c in checks):
        status = "rot"
    else:
        status = "offen"

    hinweise = list(erg.hinweise)
    if req and req.get("anmerkung"):
        hinweise.append("DIN-Anmerkung: " + req["anmerkung"])

    return NachweisZeile(
        bauteil_id=bt.id, typ=bt.typ.value, din_rolle=bt.din_rolle, bezeichnung=bezeichnung,
        tabelle_zeile=tz, erf_rw=erf_rw, vorh_rw=vorh_rw, rw_ok=rw_ok,
        zul_lnw=zul_lnw, vorh_lnw=vorh_lnw, lnw_ok=lnw_ok, status=status,
        ergebnis=erg, hinweise=hinweise,
    )


def fuehre_nachweis(projekt: Projekt, k_flanke_luft: float = 2.0,
                    m_flank_mittel: float | None = None) -> NachweisErgebnis:
    res = NachweisErgebnis(projekt=projekt)
    m_flank = m_flank_mittel if m_flank_mittel is not None else mittlere_flankenmasse(projekt)
    for bt in projekt.bauteile:
        res.zeilen.append(_pruefe_bauteil(bt, k_flanke_luft, m_flank))
    if res.anzahl_rot > 0:
        res.gesamt_status = "rot"
    elif res.anzahl_offen > 0:
        res.gesamt_status = "offen"
    elif res.zeilen:
        res.gesamt_status = "gruen"
    return res
