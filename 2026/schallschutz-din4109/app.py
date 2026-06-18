"""Streamlit-Demo: Schallschutznachweis DIN 4109 aus Bauplaenen.

    streamlit run app.py

Workflow: Plan hochladen -> Claude-Vision-Extraktion -> Modell pruefen/korrigieren (HITL)
          -> DIN-4109-Nachweis -> Report/Export herunterladen.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from schallschutz import Bauteil, Projekt, Schicht, fuehre_nachweis  # noqa: E402
from schallschutz.empfehlung import auswertung  # noqa: E402
from schallschutz.export import export_excel, export_json  # noqa: E402
from schallschutz.knowledge import requirements  # noqa: E402
from schallschutz.rechengang import export_rechengang_excel  # noqa: E402
from schallschutz.raumdaten_export import export_raumdaten_excel  # noqa: E402
from schallschutz.report import render_html  # noqa: E402
from schallschutz.visualize import wand_label  # noqa: E402  (Overlay-Vorschau zurückgenommen)

st.set_page_config(page_title="Schallschutznachweis DIN 4109", page_icon="🔇", layout="wide")

_STATUS_BADGE = {
    "gruen": ("✅ erfüllt", "#1a7f37"),
    "rot": ("❌ nicht erfüllt", "#cf222e"),
    "offen": ("⚠️ offen", "#9a6700"),
}


def _init():
    st.session_state.setdefault("projekt_json", None)
    st.session_state.setdefault("plan_bild", None)
    st.session_state.setdefault("roh_extrakt", None)


def _projekt() -> Projekt | None:
    if st.session_state.projekt_json is None:
        return None
    return Projekt.model_validate_json(st.session_state.projekt_json)


def _set_projekt(p: Projekt):
    st.session_state.projekt_json = p.model_dump_json()


def _ergebnis_karte(z, raum_namen: dict):
    """Ergebniskarte für ein einzelnes Bauteil: Status, Werte, Aufbau, Live-Rechengang."""
    e = z.ergebnis
    keine_anforderung = z.din_rolle is None and z.erf_rw is None and z.zul_lnw is None
    if keine_anforderung:
        txt, farbe = "ℹ️ kein nachweispflichtiges Trennbauteil (R′w informativ)", "#57606A"
    else:
        txt, farbe = _STATUS_BADGE[z.status]
    st.markdown(
        f"<div style='padding:12px 18px;border-radius:8px;background:{farbe};color:#fff;"
        f"font-size:17px;font-weight:700;margin:6px 0'>"
        f"{z.bauteil_id} — {z.bezeichnung} &nbsp;·&nbsp; {txt}</div>",
        unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    if e.masse_kg_m2:
        c1.metric("m′ (flächenbez. Masse)", f"{e.masse_kg_m2:.0f} kg/m²")
    if z.vorh_rw is not None:
        if z.erf_rw is not None:
            c2.metric("R′w  (vorh. / erf.)", f"{z.vorh_rw} / {z.erf_rw} dB",
                      delta=f"{z.vorh_rw - z.erf_rw:+.1f} dB ggü. erf.")
        else:
            c2.metric("R′w  (vorhanden)", f"{z.vorh_rw} dB", help="kein DIN-Anforderungswert")
    if z.vorh_lnw is not None:
        if z.zul_lnw is not None:
            c3.metric("L′n,w  (vorh. / zul.)", f"{z.vorh_lnw} / {z.zul_lnw} dB",
                      delta=f"{z.zul_lnw - z.vorh_lnw:+.1f} dB Reserve")
        else:
            c3.metric("L′n,w  (vorhanden)", f"{z.vorh_lnw} dB")

    if e.schichten:
        aufbau = "  ·  ".join(
            f"{s.material} {s.dicke_mm:.0f} mm" + (f" (ρ={s.rohdichte:.0f})" if s.rohdichte else "")
            + ("" if s.in_masse else "  [schwimmend, nicht in m′]")
            for s in e.schichten)
        st.markdown(f"**Aufbau:** {aufbau}")

    # Begründung + Verbesserungsvorschläge bei Nichterfüllung / offen
    gruende, massnahmen = auswertung(z)
    if gruende or massnahmen:
        box = st.error if z.status == "rot" else st.warning
        inhalt = ""
        if gruende:
            inhalt += "**Warum nicht erfüllt:**\n" + "\n".join(f"- {g}" for g in gruende)
        if massnahmen:
            inhalt += ("\n\n" if inhalt else "") + "**Was man besser machen kann:**\n" + \
                      "\n".join(f"- {m}" for m in massnahmen)
        box(inhalt)

    st.markdown("**Rechengang (DIN 4109):**")
    st.code("\n".join(e.formeln) if e.formeln else "—", language="text")
    for h in z.hinweise:
        st.caption(f"⚠️ {h}")


def _raum_bewertung(raum_id, teile, zeilen, raum_namen):
    """Bewertung des GANZEN Raums: alle nachweispflichtigen Bauteile + Gesamturteil + Begründungen."""
    zz = [zeilen[b.id] for b in teile if b.id in zeilen]
    pflicht = [z for z in zz if z.din_rolle]
    rot = sum(1 for z in pflicht if z.status == "rot")
    offen = sum(1 for z in pflicht if z.status == "offen")
    status = "gruen" if (pflicht and rot == 0 and offen == 0) else ("rot" if rot else ("offen" if offen else "gruen"))
    txt, farbe = _STATUS_BADGE[status]
    name = raum_namen.get(raum_id, raum_id)
    st.markdown(
        f"<div style='padding:12px 18px;border-radius:8px;background:{farbe};color:#fff;"
        f"font-size:17px;font-weight:700;margin:6px 0'>Raum: {name} — {txt} "
        f"<span style='font-size:14px;font-weight:500'>({len(pflicht)} nachweispflichtige Bauteile)</span></div>",
        unsafe_allow_html=True)

    if not pflicht:
        st.info("Keine nachweispflichtigen Trennbauteile in diesem Raum (nur Innen-/Außenwände ohne DIN-Anforderung).")
    else:
        import pandas as pd
        rows = [{
            "ID": z.bauteil_id, "Bauteil": z.bezeichnung, "DIN": z.tabelle_zeile,
            "erf. R′w": z.erf_rw, "vorh. R′w": z.vorh_rw,
            "zul. L′n,w": z.zul_lnw, "vorh. L′n,w": z.vorh_lnw,
            "Ergebnis": _STATUS_BADGE[z.status][0],
        } for z in pflicht]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        for z in pflicht:
            if z.status == "gruen":
                continue
            gruende, massnahmen = auswertung(z)
            with st.expander(f"❗ {z.bauteil_id} — {z.bezeichnung}  ·  {_STATUS_BADGE[z.status][0]}", expanded=True):
                if gruende:
                    st.markdown("**Warum nicht erfüllt:**\n" + "\n".join(f"- {g}" for g in gruende))
                if massnahmen:
                    st.markdown("**Was man besser machen kann:**\n" + "\n".join(f"- {m}" for m in massnahmen))


def _material_optionen():
    """(keys, labels) aller Katalog-Materialien, nach Kategorie sortiert, lesbar beschriftet."""
    from schallschutz.knowledge import materials
    items = sorted(materials().items(), key=lambda kv: (kv[1]["kategorie"], kv[0]))
    keys = [k for k, _ in items]
    labels = {k: f"{v['kategorie']} · {k}  (ρ={v['rohdichte']} kg/m³)" for k, v in items}
    return keys, labels


def _kern_index(bt):
    """Index der tragenden Schicht (größte Massekurven-Masse), sonst 0 / None."""
    from schallschutz.engine import _CURVE_CATS
    from schallschutz.knowledge import resolve_material
    best = None
    for i, s in enumerate(bt.schichten):
        key, mat = resolve_material(s.material)
        if mat and mat["kategorie"] in _CURVE_CATS:
            masse = (s.dicke_mm / 1000.0) * (s.rohdichte_override or mat["rohdichte"])
            if best is None or masse > best[1]:
                best = (i, masse)
    if best:
        return best[0]
    return 0 if bt.schichten else None


# ----------------------------------------------------------------------------- Sidebar
_init()
st.sidebar.title("🔇 DIN 4109")
st.sidebar.caption("Schallschutznachweis aus Bauplänen — KI-gestützt")
st.sidebar.divider()
k_luft = st.sidebar.slider("Flankenkorrektur Luftschall K (dB)", 0.0, 6.0, 2.0, 0.5,
                           help="Vereinfachte Flankenübertragung (DIN 4109-2). Exakter 4-Wege-Nachweis = Ausbaustufe.")
auto_flank = st.sidebar.checkbox("m′f,m automatisch aus Modell-Wänden", value=True,
                                 help="Mittlere Flankenmasse für Trittschall-K nach DIN 4109-2 Gl.26.")
m_flank_manual = st.sidebar.slider("m′f,m flankierende Masse (kg/m²)", 100.0, 500.0, 300.0, 10.0,
                                   disabled=auto_flank)
st.sidebar.divider()
st.sidebar.markdown(
    "**Pipeline**\n\n"
    "1. Plan (PDF/Bild) → **Claude Vision**\n"
    "2. Modell prüfen/korrigieren (HITL)\n"
    "3. **DIN-Engine** (deterministisch)\n"
    "4. Report + Software-Export"
)
_modelle = [
    ("🔁 Demo-Modell (Einzelplan)", ROOT / "outputs" / "extrahiertes_modell.json",
     ROOT / "examples" / "plan_demo.png"),
    ("🏢 Echtplan-Modell (Ausführungsplan)", ROOT / "outputs" / "real_modell.json", None),
    ("📄 Beispiel-Inputs (Plan+Legende+Schnitt)", ROOT / "outputs" / "beispiel_modell.json",
     ROOT / "outputs" / "beispiel_plan_preview.png"),
]
_verfuegbar = [(lbl, pf, img) for lbl, pf, img in _modelle if pf.exists()]
if _verfuegbar:
    st.sidebar.divider()
    st.sidebar.caption("Schnell laden (ohne Live-Call):")
    for lbl, pf, img in _verfuegbar:
        if st.sidebar.button(lbl):
            st.session_state.projekt_json = pf.read_text(encoding="utf-8")
            st.session_state.plan_bild = str(img) if (img and img.exists()) else None
            st.sidebar.success("Geladen → weiter zu Tab 2 (Raum → Wand).")

# ----------------------------------------------------------------------------- Header
st.title("Schallschutznachweis nach DIN 4109")
st.caption("Automatische Extraktion von Geometrie, Bauteilen & Materialien aus Architekturzeichnungen "
           "und Nachweisführung Luft- + Trittschall.")

tab_input, tab_ziel, tab_modell, tab_nachweis = st.tabs(
    ["1 · Plan & Extraktion", "2 · ★ Raum → Wand → Ergebnis", "3 · Modell prüfen", "4 · Gesamt-Nachweis & Export"])

# ============================================================================= TAB 1
with tab_input:
    col_l, col_r = st.columns([1, 1])
    with col_l:
        st.subheader("Plan laden")
        quelle = st.radio("Quelle", ["Demo-Plan (Einzelbild)", "Ausführungsplan (echt, gekachelt)",
                                      "Eigenen Plan hochladen", "Modell-JSON laden"],
                          label_visibility="collapsed")
        plan_path = None

        if quelle == "Demo-Plan (Einzelbild)":
            plan_path = ROOT / "examples" / "plan_demo.png"
            st.info(f"Demo-Plan: `{plan_path.name}`")

        elif quelle == "Eigenen Plan hochladen":
            up = st.file_uploader("Grundriss / Schnitt (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"])
            if up:
                plan_path = ROOT / "outputs" / f"upload_{up.name}"
                plan_path.parent.mkdir(exist_ok=True)
                plan_path.write_bytes(up.getbuffer())

        elif quelle == "Modell-JSON laden":
            upj = st.file_uploader("Gebäudemodell (JSON)", type=["json"])
            if upj:
                st.session_state.projekt_json = upj.getvalue().decode("utf-8")
                st.success("Modell geladen — weiter zu Tab 2.")

        else:  # Ausführungsplan (echt, gekachelt)
            real_dir = ROOT / "examples" / "real_plans"
            bundled = sorted(p.name for p in real_dir.glob("*.pdf")) if real_dir.exists() else []
            st.caption("Lade **Plan + Legende (+ Schnitt)** als getrennte PDFs hoch. "
                       "Fertige Beispiel-Inputs liegen in `examples/beispiel_inputs/`.")
            up_plan = st.file_uploader("① Plan / Grundriss-Ausschnitt (PDF)", type=["pdf"])
            up_legend = st.file_uploader("② Legende (PDF/Bild)", type=["pdf", "png", "jpg", "jpeg"],
                                         help="Material-Schlüssel (Schraffuren). Wird statt Auto-Zuschnitt verwendet.")
            up_schnitt = st.file_uploader("③ Schnitt (PDF, optional — für Deckenaufbau)", type=["pdf"])
            grundriss = st.selectbox("…oder gebündelten Gesamtplan wählen", ["(keiner)"] + bundled) if bundled else None
            c1, c2 = st.columns(2)
            nx = c1.selectbox("Kacheln X", [1, 2, 3], index=0)
            ny = c2.selectbox("Kacheln Y", [1, 2, 3], index=0)
            dpi = st.select_slider("DPI", [200, 250, 300, 350], value=300)
            st.caption(f"≈ {1 + nx*ny + (1 if up_schnitt else 0)} Claude-Vision-Calls")

            if st.button("🧩 Extrahieren (Plan + Legende + Schnitt)", type="primary"):
                from schallschutz.extraction.real_plan import extrahiere_real_plan, DEFAULT_PLAN_BBOX
                plan_pdf = None
                if up_plan:
                    plan_pdf = ROOT / "outputs" / f"upload_{up_plan.name}"
                    plan_pdf.write_bytes(up_plan.getbuffer())
                elif grundriss and grundriss != "(keiner)":
                    plan_pdf = real_dir / grundriss
                # separat hochgeladene Eingaben
                legend_path = None
                if up_legend:
                    legend_path = ROOT / "outputs" / f"legend_{up_legend.name}"
                    legend_path.write_bytes(up_legend.getbuffer())
                schnitt_pdf = None
                if up_schnitt:
                    schnitt_pdf = ROOT / "outputs" / f"schnitt_{up_schnitt.name}"
                    schnitt_pdf.write_bytes(up_schnitt.getbuffer())
                # Wenn Legende separat kommt, enthaelt der Plan keine Legende -> Vollseite auslesen
                plan_bbox = (0.0, 0.0, 1.0, 1.0) if legend_path else DEFAULT_PLAN_BBOX
                if plan_pdf:
                    box = st.status("Extraktion läuft …", expanded=True)
                    try:
                        projekt, roh, images = extrahiere_real_plan(
                            plan_pdf, grid=(nx, ny), dpi=dpi, plan_bbox=plan_bbox,
                            schnitt_pdf=schnitt_pdf, legend_image=legend_path,
                            progress=lambda m: box.write(m))
                        _set_projekt(projekt)
                        st.session_state.roh_extrakt = roh
                        if images:
                            st.session_state.plan_bild = str(images[0])
                        box.update(label="Fertig", state="complete")
                        st.success(f"Extrahiert: {len(projekt.raeume)} Räume, "
                                   f"{len(projekt.nutzungseinheiten)} Wohnungen, "
                                   f"{len(projekt.bauteile)} Bauteile. → Tab 2 zum Prüfen.")
                    except Exception as e:
                        box.update(label="Fehler", state="error")
                        st.error(f"Extraktion fehlgeschlagen: {e}")

        if plan_path and plan_path.suffix.lower() in (".png", ".jpg", ".jpeg"):
            st.session_state.plan_bild = str(plan_path)

        if plan_path and st.button("🔍 Mit Claude Vision extrahieren", type="primary"):
            from schallschutz.extraction import extrahiere_modell
            with st.spinner("Claude liest den Plan und extrahiert Räume, Bauteile, Materialien …"):
                try:
                    projekt, roh, images = extrahiere_modell(plan_path)
                    _set_projekt(projekt)
                    st.session_state.roh_extrakt = roh
                    if images:
                        st.session_state.plan_bild = str(images[0])
                    st.success(f"Extrahiert: {len(projekt.raeume)} Räume, {len(projekt.bauteile)} Bauteile. "
                               "→ Tab 2 zum Prüfen.")
                except Exception as e:
                    st.error(f"Extraktion fehlgeschlagen: {e}")

    with col_r:
        st.subheader("Planvorschau")
        if st.session_state.plan_bild and Path(st.session_state.plan_bild).exists():
            st.image(st.session_state.plan_bild, use_container_width=True)
        else:
            st.caption("Noch kein Plan geladen.")

# ============================================================ TAB ZIEL (Hauptziel)
with tab_ziel:
    p = _projekt()
    if p is None:
        st.info("Noch kein Modell — bitte in Tab 1 einen Plan extrahieren.")
    elif not p.raeume:
        st.warning("Keine Räume im Modell.")
    else:
        st.subheader("Raum wählen → bewerten (ganzer Raum oder einzelne Wand)")
        res = fuehre_nachweis(p, k_flanke_luft=k_luft,
                              m_flank_mittel=None if auto_flank else m_flank_manual)
        zeilen = {z.bauteil_id: z for z in res.zeilen}
        raum_namen = {r.id: r.name for r in p.raeume}

        modus = st.radio("Was bewerten?", ["Einzelne Wand", "Ganzer Raum"], horizontal=True)
        raum_id = st.selectbox("🏠 Raum", options=[r.id for r in p.raeume],
                               format_func=lambda i: raum_namen.get(i, i))
        teile = [b for b in p.bauteile if raum_id in (b.raum_a, b.raum_b)]
        if not teile:
            st.caption("Keine raumzugeordneten Bauteile — Auswahl aus allen.")
            teile = p.bauteile
        st.divider()

        if modus == "Ganzer Raum":
            _raum_bewertung(raum_id, teile, zeilen, raum_namen)
        else:
            def _label(bid):
                b = next(x for x in teile if x.id == bid)
                return wand_label(b, raum_namen)

            bt_id = st.selectbox("🧱 Wand / Bauteil", options=[b.id for b in teile], format_func=_label)
            z = zeilen.get(bt_id)
            if z is None:
                st.info("Für dieses Bauteil liegt kein Ergebnis vor.")
            else:
                _ergebnis_karte(z, raum_namen)

                # --- Human-in-the-Loop: Wandart / Material bestätigen oder korrigieren ---
                bt = next((b for b in p.bauteile if b.id == bt_id), None)
                if bt is not None and bt.typ.value in ("wand", "decke"):
                    with st.expander("✏️ Wandart / Material bestätigen oder korrigieren (Human-in-the-Loop)",
                                     expanded=False):
                        st.caption("Die KI-Materialerkennung ist nur ein Vorschlag. Hier bestätigst oder änderst "
                                   "du die tragende Schicht (z. B. *ist es Mauerwerk? welches?*) — Ergebnis rechnet neu.")
                        keys, labels = _material_optionen()
                        ci = _kern_index(bt)
                        from schallschutz.knowledge import resolve_material
                        cur_key = None
                        if ci is not None and bt.schichten:
                            cur_key, _ = resolve_material(bt.schichten[ci].material)
                        idx = keys.index(cur_key) if cur_key in keys else 0
                        cur_dicke = (bt.schichten[ci].dicke_mm / 10) if (ci is not None and bt.schichten) else 17.5

                        e1, e2 = st.columns([3, 1])
                        neu_mat = e1.selectbox("Tragendes Material (Wandart)", keys, index=idx,
                                               format_func=lambda k: labels[k])
                        neu_dicke = e2.number_input("Dicke [cm]", 1.0, 60.0, float(round(cur_dicke, 1)), 0.5)
                        if st.button("✓ Übernehmen & neu berechnen", type="primary"):
                            pp = _projekt()
                            b2 = next(x for x in pp.bauteile if x.id == bt_id)
                            if b2.schichten and ci is not None:
                                b2.schichten[ci].material = neu_mat
                                b2.schichten[ci].dicke_mm = neu_dicke * 10
                                b2.schichten[ci].rohdichte_override = None
                            else:
                                b2.schichten = [Schicht(material=neu_mat, dicke_mm=neu_dicke * 10)]
                            _set_projekt(pp)
                            st.rerun()

# ============================================================================= TAB 2
with tab_modell:
    p = _projekt()
    if p is None:
        st.info("Noch kein Modell. Bitte in Tab 1 einen Plan extrahieren oder ein Modell-JSON laden.")
    else:
        st.subheader("Extrahiertes Gebäudemodell — prüfen & korrigieren (Human-in-the-Loop)")
        c1, c2, c3 = st.columns(3)
        c1.metric("Räume", len(p.raeume))
        c2.metric("Bauteile", len(p.bauteile))
        c3.metric("Gebäudetyp", p.gebaeude.typ.value)

        st.markdown("**Räume**")
        st.dataframe(pd.DataFrame([r.model_dump() for r in p.raeume]), use_container_width=True, hide_index=True)

        st.markdown("**Bauteile** — `din_rolle`, Schichten (JSON), ΔRw/ΔLw und Tür-Rw sind editierbar:")
        rollen = [""] + list(requirements().keys())
        rows = []
        for bt in p.bauteile:
            rows.append({
                "id": bt.id, "typ": bt.typ.value, "din_rolle": bt.din_rolle or "",
                "schichten_json": json.dumps([s.model_dump(exclude_none=True) for s in bt.schichten], ensure_ascii=False),
                "delta_rw_vorsatz": bt.delta_rw_vorsatz, "delta_lw": bt.delta_lw,
                "rw_element": bt.rw_element, "verschiedene_einheiten": bt.verschiedene_einheiten,
                "bemerkung": bt.bemerkung or "",
            })
        edited = st.data_editor(
            pd.DataFrame(rows), use_container_width=True, hide_index=True, num_rows="dynamic",
            column_config={
                "din_rolle": st.column_config.SelectboxColumn("din_rolle", options=rollen, width="medium"),
                "schichten_json": st.column_config.TextColumn("schichten_json", width="large"),
            },
        )

        if st.button("💾 Korrekturen übernehmen"):
            try:
                neue = []
                for _, r in edited.iterrows():
                    schichten = json.loads(r["schichten_json"] or "[]")
                    neue.append(Bauteil(
                        id=str(r["id"]), typ=str(r["typ"]),
                        din_rolle=(r["din_rolle"] or None),
                        schichten=schichten,
                        delta_rw_vorsatz=float(r["delta_rw_vorsatz"] or 0),
                        delta_lw=float(r["delta_lw"] or 0),
                        rw_element=(float(r["rw_element"]) if pd.notna(r["rw_element"]) and r["rw_element"] != "" else None),
                        verschiedene_einheiten=bool(r["verschiedene_einheiten"]),
                        bemerkung=(r["bemerkung"] or None),
                    ))
                p.bauteile = neue
                _set_projekt(p)
                st.success("Modell aktualisiert. → Tab 3 für den Nachweis.")
            except Exception as e:
                st.error(f"Konnte Korrekturen nicht übernehmen: {e}")

# ============================================================================= TAB 3
with tab_nachweis:
    p = _projekt()
    if p is None:
        st.info("Noch kein Modell. Bitte zuerst Tab 1/2.")
    else:
        res = fuehre_nachweis(p, k_flanke_luft=k_luft,
                              m_flank_mittel=None if auto_flank else m_flank_manual)
        txt, farbe = _STATUS_BADGE[res.gesamt_status]
        st.markdown(
            f"<div style='padding:14px 20px;border-radius:8px;background:{farbe};color:#fff;"
            f"font-size:20px;font-weight:700;display:flex;justify-content:space-between'>"
            f"<span>Gesamtergebnis: {txt}</span>"
            f"<span style='font-size:15px;font-weight:500'>{res.anzahl_ok} erfüllt · "
            f"{res.anzahl_rot} nicht erfüllt · {res.anzahl_offen} offen</span></div>",
            unsafe_allow_html=True)
        st.write("")

        tabelle = []
        for z in res.zeilen:
            badge = _STATUS_BADGE[z.status][0]
            tabelle.append({
                "ID": z.bauteil_id, "Bauteil": z.bezeichnung, "DIN": z.tabelle_zeile,
                "m′ [kg/m²]": z.ergebnis.masse_kg_m2,
                "erf. R′w": z.erf_rw, "vorh. R′w": z.vorh_rw,
                "zul. L′n,w": z.zul_lnw, "vorh. L′n,w": z.vorh_lnw,
                "Ergebnis": badge,
            })
        st.dataframe(pd.DataFrame(tabelle), use_container_width=True, hide_index=True)

        with st.expander("📐 Berechnungsdetails & Hinweise je Bauteil"):
            for z in res.zeilen:
                st.markdown(f"**{z.bauteil_id} — {z.bezeichnung}** ({_STATUS_BADGE[z.status][0]})")
                if z.ergebnis.formeln:
                    st.code("\n".join(z.ergebnis.formeln), language="text")
                for h in z.hinweise:
                    st.caption(f"⚠️ {h}")
                st.divider()

        st.subheader("Export")
        st.caption("Der **Rechengang (Excel)** enthält Eingabeparameter, Formeln und die Berechnung "
                   "mit echten Live-Excel-Formeln — jede Zahl ist nachvollziehbar und änderbar.")
        _XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        d1, d2, d3, d4, d5 = st.columns(5)
        html = render_html(res)
        d1.download_button("⬇️ Report (HTML)", html, file_name="nachweis_din4109.html", mime="text/html")
        rg_path = export_rechengang_excel(res, ROOT / "outputs" / "_rg.xlsx")
        d2.download_button("⬇️ Rechengang (Excel)", rg_path.read_bytes(),
                           file_name="rechengang_din4109.xlsx", mime=_XLSX)
        rd_path = export_raumdaten_excel(p, ROOT / "outputs" / "_rd.xlsx")
        d3.download_button("⬇️ Raumdaten (Excel)", rd_path.read_bytes(),
                           file_name="raumdaten.xlsx", mime=_XLSX,
                           help="Raum-zentrisch, Wände einklappbar, mit Dropdowns (Bezug/Material)")
        xlsx_path = export_excel(res, ROOT / "outputs" / "_dl.xlsx")
        d4.download_button("⬇️ Software-Eingabe (Excel)", xlsx_path.read_bytes(),
                           file_name="eingabe_schallschutzsoftware.xlsx", mime=_XLSX)
        json_path = export_json(res, ROOT / "outputs" / "_dl.json")
        d5.download_button("⬇️ Modell (JSON)", json_path.read_bytes(),
                           file_name="nachweis_din4109.json", mime="application/json")
