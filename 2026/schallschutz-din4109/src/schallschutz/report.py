"""Erzeugt einen strukturierten Schallschutznachweis als eigenstaendiges HTML (druckbar -> PDF)."""
from __future__ import annotations

import html
from datetime import date
from pathlib import Path

from .nachweis import NachweisErgebnis, NachweisZeile

_STATUS_FARBE = {"gruen": "#1a7f37", "rot": "#cf222e", "offen": "#9a6700"}
_STATUS_TEXT = {"gruen": "ERFUELLT", "rot": "NICHT ERFUELLT", "offen": "PRUEFUNG OFFEN"}
_STATUS_BANNER = {"gruen": "Nachweis erfuellt", "rot": "Nachweis NICHT erfuellt", "offen": "Nachweis unvollstaendig"}


def _e(x) -> str:
    return html.escape(str(x)) if x is not None else "&ndash;"


def _zeile_html(z: NachweisZeile) -> str:
    farbe = _STATUS_FARBE[z.status]
    erf = f"&ge; {z.erf_rw:.0f}" if z.erf_rw is not None else "&ndash;"
    vrw = f"{z.vorh_rw:.1f}" if z.vorh_rw is not None else "&ndash;"
    zul = f"&le; {z.zul_lnw:.0f}" if z.zul_lnw is not None else "&ndash;"
    vln = f"{z.vorh_lnw:.1f}" if z.vorh_lnw is not None else "&ndash;"

    aufbau = " &middot; ".join(
        f"{_e(s.material)} {s.dicke_mm:.0f}&thinsp;mm"
        + (f" (&rho;={s.rohdichte:.0f})" if s.rohdichte else "")
        for s in z.ergebnis.schichten
    ) or "&ndash;"

    masse = f"{z.ergebnis.masse_kg_m2:.0f} kg/m&sup2;" if z.ergebnis.masse_kg_m2 else "&ndash;"
    formeln = "<br>".join(_e(f) for f in z.ergebnis.formeln) or "&ndash;"
    hinweise = "".join(f"<div class='hint'>&#9888; {_e(h)}</div>" for h in z.hinweise)

    return f"""
    <tr class="head">
      <td><b>{_e(z.bauteil_id)}</b></td>
      <td>{_e(z.bezeichnung)}<div class="sub">{_e(z.tabelle_zeile)} &middot; Typ: {_e(z.typ)}</div></td>
      <td class="num">{erf}</td><td class="num">{vrw}</td>
      <td class="num">{zul}</td><td class="num">{vln}</td>
      <td class="status" style="color:{farbe}"><b>{_STATUS_TEXT[z.status]}</b></td>
    </tr>
    <tr class="detail">
      <td></td>
      <td colspan="6">
        <div class="aufbau"><b>Aufbau:</b> {aufbau} &nbsp;|&nbsp; <b>m&prime;:</b> {masse}</div>
        <div class="formeln"><b>Berechnung:</b><br>{formeln}</div>
        {hinweise}
      </td>
    </tr>"""


def render_html(res: NachweisErgebnis) -> str:
    p = res.projekt
    banner = _STATUS_BANNER[res.gesamt_status]
    bfarbe = _STATUS_FARBE[res.gesamt_status]
    zeilen = "\n".join(_zeile_html(z) for z in res.zeilen)

    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<title>Schallschutznachweis DIN 4109 &ndash; {_e(p.name)}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Segoe UI", Arial, sans-serif; color: #1c2128; margin: 0; padding: 32px 40px; font-size: 13px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .meta {{ color: #57606a; margin-bottom: 20px; }}
  .meta b {{ color: #1c2128; }}
  .banner {{ padding: 14px 20px; border-radius: 8px; color: #fff; font-size: 18px; font-weight: 700;
             background: {bfarbe}; margin: 18px 0 24px; display: flex; justify-content: space-between; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #f6f8fa; text-align: left; padding: 8px 10px; border-bottom: 2px solid #d0d7de; font-size: 12px; }}
  th.num, td.num {{ text-align: right; }}
  td {{ padding: 7px 10px; vertical-align: top; }}
  tr.head td {{ border-top: 1px solid #d8dee4; }}
  tr.detail td {{ padding-top: 0; color: #57606a; font-size: 12px; }}
  .sub {{ color: #8b949e; font-size: 11px; }}
  .aufbau {{ margin-bottom: 4px; }}
  .formeln {{ font-family: "Consolas", monospace; font-size: 11px; background: #f6f8fa; padding: 6px 8px;
             border-radius: 5px; margin: 4px 0; }}
  .hint {{ color: #9a6700; margin-top: 3px; }}
  .status {{ white-space: nowrap; }}
  .legend {{ margin-top: 28px; padding-top: 16px; border-top: 1px solid #d0d7de; color: #57606a; font-size: 11px; }}
  .legend code {{ background:#f6f8fa; padding:1px 4px; border-radius:3px; }}
</style></head>
<body>
  <h1>Schallschutznachweis nach DIN 4109</h1>
  <div class="meta">
    <b>{_e(p.name)}</b><br>
    Bauvorhaben: {_e(p.bauvorhaben)}<br>
    Gebaeudetyp: {_e(p.gebaeude.typ.value)} &middot; Geschosse: {_e(p.gebaeude.geschosse)}
    &middot; Datenquelle: {_e(p.quelle_plan)}<br>
    Bearbeiter: {_e(p.bearbeiter)} &middot; Datum: {date.today().isoformat()}
  </div>

  <div class="banner"><span>{banner}</span>
    <span>{res.anzahl_ok} erfuellt &middot; {res.anzahl_rot} nicht erfuellt &middot; {res.anzahl_offen} offen</span></div>

  <table>
    <thead><tr>
      <th>ID</th><th>Bauteil / Anforderung</th>
      <th class="num">erf. R&prime;w</th><th class="num">vorh. R&prime;w</th>
      <th class="num">zul. L&prime;n,w</th><th class="num">vorh. L&prime;n,w</th>
      <th>Ergebnis</th>
    </tr></thead>
    <tbody>{zeilen}</tbody>
  </table>

  <div class="legend">
    <b>Methodik &amp; Quellen:</b> Anforderungen nach <code>DIN 4109-1:2018-01</code> (Tab. 2/3).
    Flaechenbez. Masse <code>m&prime; = d&middot;&rho;</code> und bew. Schalldaemm-Mass
    <code>R_w</code> nach <code>DIN 4109-32:2016-07</code> (Gl. 13&ndash;16).
    Norm-Trittschallpegel <code>L_n,eq,0,w = 164 &minus; 35&middot;lg(m&prime;)</code> (Gl. 21).
    Eingebaute Werte <code>R&prime;w</code> / <code>L&prime;n,w</code> nach <code>DIN 4109-2</code>
    (Vorsatzschale &Delta;R_w, Estrich &Delta;L_w nach <code>DIN 4109-34</code>; Flankenuebertragung vereinfacht).
    Rohdichten: Rechenwerte nach DIN 4109-32 / DIN EN ISO 10456.
    <br><br><i>Proof of Concept &ndash; ersetzt keinen geprueften bauakustischen Nachweis.
    Der exakte Flankennachweis nach DIN 4109-2 (4 Flankenwege) ist als Ausbaustufe vorgesehen.</i>
  </div>
</body></html>"""


def schreibe_report(res: NachweisErgebnis, pfad: str | Path) -> Path:
    pfad = Path(pfad)
    pfad.write_text(render_html(res), encoding="utf-8")
    return pfad
