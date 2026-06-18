"""Auswertung je Bauteil: WARUM nicht erfuellt + konkrete Verbesserungsvorschlaege (deterministisch)."""
from __future__ import annotations

import math

from .engine import K_FLANKE_LUFT_DEFAULT, masse_fuer_rw
from .nachweis import NachweisZeile


def auswertung(z: NachweisZeile) -> tuple[list[str], list[str]]:
    """Liefert (gruende, massnahmen). Leer, wenn alles erfuellt."""
    gruende: list[str] = []
    massnahmen: list[str] = []
    e = z.ergebnis

    # --- Luftschall nicht erfuellt ---
    if z.erf_rw is not None and z.vorh_rw is not None and z.vorh_rw < z.erf_rw:
        d = z.erf_rw - z.vorh_rw
        gruende.append(f"Luftschalldämmung R′w = {z.vorh_rw:.1f} dB < erforderlich {z.erf_rw:.0f} dB "
                       f"(Fehlbetrag {d:.1f} dB).")
        massnahmen.append(f"Vorsatzschale mit ΔRw ≥ {math.ceil(d)} dB ergänzen (DIN 4109-34).")
        if e.massekurve and e.masse_kg_m2:
            k = e.k_luft if e.k_luft is not None else K_FLANKE_LUFT_DEFAULT
            m_need = masse_fuer_rw(z.erf_rw + k, e.massekurve)
            if m_need:
                massnahmen.append(
                    f"Oder Masse erhöhen: m′ von {e.masse_kg_m2:.0f} auf ≥ {m_need:.0f} kg/m² "
                    f"(dickere Wand oder höhere Rohdichteklasse, z. B. KS 2.0 statt 1.8).")

    # --- Trittschall nicht erfuellt ---
    if z.zul_lnw is not None and z.vorh_lnw is not None and z.vorh_lnw > z.zul_lnw:
        d = z.vorh_lnw - z.zul_lnw
        gruende.append(f"Trittschallpegel L′n,w = {z.vorh_lnw:.1f} dB > zulässig {z.zul_lnw:.0f} dB "
                       f"(Überschreitung {d:.1f} dB).")
        cur = e.dlw_verwendet or 0
        massnahmen.append(
            f"Schwimmenden Estrich / Bodenbelag mit ΔLw ≥ {math.ceil(cur + d)} dB vorsehen "
            f"(aktuell {cur:.0f} dB, DIN 4109-34).")
        if e.schwimmender_estrich is False:
            massnahmen.append("Decke ohne schwimmenden Boden — schwimmenden Estrich auf Trittschalldämmung ergänzen.")

    # --- unvollstaendig (offen) ---
    if z.status == "offen":
        if z.erf_rw is not None and z.vorh_rw is None:
            gruende.append("R′w nicht berechenbar — Material/Aufbau der tragenden Schicht fehlt.")
        if z.zul_lnw is not None and z.vorh_lnw is None:
            gruende.append("L′n,w nicht berechenbar — Deckenaufbau (Rohdecke/Estrich) fehlt.")
        if not z.din_rolle:
            gruende.append("Keine DIN-Rolle zugeordnet — Bauteil ist evtl. nicht nachweispflichtig.")
        massnahmen.append("Fehlende Angaben im Schritt „Material/Wandart bestätigen“ (HITL) ergänzen.")

    return gruende, massnahmen
