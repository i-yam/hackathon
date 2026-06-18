"""CLI: laedt ein Gebaeudemodell (JSON), fuehrt den DIN-4109-Nachweis und gibt eine Tabelle aus.

    python run_nachweis.py examples/example_model.json
"""
from __future__ import annotations

import sys
from pathlib import Path

try:  # Windows-Konsole auf UTF-8 (sonst cp1252-Fehler bei Sonderzeichen)
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from schallschutz import Projekt, fuehre_nachweis  # noqa: E402

_AMPEL = {"gruen": "[ OK ]", "rot": "[FAIL]", "offen": "[OFFEN]"}


def main() -> None:
    pfad = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("examples/example_model.json")
    projekt = Projekt.model_validate_json(pfad.read_text(encoding="utf-8"))
    res = fuehre_nachweis(projekt)

    print(f"\n=== Schallschutznachweis DIN 4109 — {projekt.name} ===")
    print(f"Bauvorhaben : {projekt.bauvorhaben}")
    print(f"Gebaeudetyp : {projekt.gebaeude.typ.value}")
    print("-" * 100)
    h_erf, h_vrw, h_zul, h_vln = "erf.R'w", "vorh.R'w", "zul.Lnw", "vorh.Lnw"
    print(f"{'ID':6} {'Bauteil':28} {h_erf:8} {h_vrw:9} {h_zul:9} {h_vln:10} Status")
    print("-" * 100)
    for z in res.zeilen:
        erf = f"{z.erf_rw:.0f}" if z.erf_rw is not None else "-"
        vrw = f"{z.vorh_rw:.1f}" if z.vorh_rw is not None else "-"
        zul = f"{z.zul_lnw:.0f}" if z.zul_lnw is not None else "-"
        vln = f"{z.vorh_lnw:.1f}" if z.vorh_lnw is not None else "-"
        name = (z.bezeichnung[:27]) if z.bezeichnung else ""
        print(f"{z.bauteil_id:6} {name:28} {erf:8} {vrw:9} {zul:9} {vln:10} {_AMPEL[z.status]}")
        for h in z.hinweise:
            print(f"       -> {h}")
    print("-" * 100)
    print(f"GESAMT: {_AMPEL[res.gesamt_status]}   "
          f"({res.anzahl_ok} erfuellt, {res.anzahl_rot} nicht erfuellt, {res.anzahl_offen} offen)\n")


if __name__ == "__main__":
    main()
