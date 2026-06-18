"""End-to-End-Demo: Plan (PDF/Bild) -> Claude-Vision-Extraktion -> DIN-4109-Nachweis -> Report.

    python demo_pipeline.py examples/plan_demo.png
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from schallschutz import fuehre_nachweis  # noqa: E402
from schallschutz.extraction import extrahiere_modell  # noqa: E402
from schallschutz.report import schreibe_report  # noqa: E402
from schallschutz.export import export_excel, export_json  # noqa: E402
from schallschutz.rechengang import export_rechengang_excel  # noqa: E402

_AMPEL = {"gruen": "[ OK ]", "rot": "[FAIL]", "offen": "[OFFEN]"}


def main() -> None:
    plan = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("examples/plan_demo.png")
    print(f"[1/3] Vision-Extraktion aus {plan.name} (Claude SDK) ...")
    projekt, roh, images = extrahiere_modell(plan)
    print(f"      -> {len(projekt.raeume)} Raeume, {len(projekt.bauteile)} Bauteile extrahiert")
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/extrahiertes_modell.json").write_text(
        projekt.model_dump_json(indent=2), encoding="utf-8")

    print("[2/3] DIN-4109-Nachweis ...")
    res = fuehre_nachweis(projekt)
    for z in res.zeilen:
        erf = f"erf.R'w>={z.erf_rw}" if z.erf_rw is not None else ""
        vrw = f"vorh={z.vorh_rw}" if z.vorh_rw is not None else ""
        ln = f"L'n,w={z.vorh_lnw}/<={z.zul_lnw}" if z.zul_lnw is not None else ""
        print(f"      {_AMPEL[z.status]} {z.bauteil_id:6} {z.bezeichnung[:34]:34} {erf:14} {vrw:10} {ln}")

    print("[3/3] Report + Export ...")
    schreibe_report(res, "outputs/nachweis.html")
    export_rechengang_excel(res, "outputs/rechengang_din4109.xlsx")
    export_excel(res, "outputs/eingabe_schallschutzsoftware.xlsx")
    export_json(res, "outputs/nachweis.json")
    print(f"\nGESAMT: {_AMPEL[res.gesamt_status]}  "
          f"({res.anzahl_ok} erfuellt, {res.anzahl_rot} nicht erfuellt, {res.anzahl_offen} offen)")
    print("Artefakte in outputs/: nachweis.html, rechengang_din4109.xlsx (transparenter Rechengang), "
          "eingabe_schallschutzsoftware.xlsx, nachweis.json, extrahiertes_modell.json")


if __name__ == "__main__":
    main()
