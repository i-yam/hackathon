# Schallschutznachweis DIN 4109 — KI-gestützt aus Bauplänen

> THWS-Hackathon: *Automating the creation of sound insulation verification reports from architectural drawings.*

Extrahiert Raumgeometrie, Bauteile und Materialien aus Architekturzeichnungen (Grundriss/Schnitt) mit **Claude Vision**, führt einen **DIN-4109-Schallschutznachweis** (Luft- + Trittschall) und erzeugt einen strukturierten **Nachweis-Report** plus **Eingabedaten-Export** für Schallschutz-Berechnungssoftware.

---

## Die Idee: 2-stufige Architektur

Bewusst **entkoppelt**, damit der bewertungsrelevante Kern unabhängig von KI-Verfügbarkeit robust bleibt:

```
   Plan (PDF/Bild)                Zwischenmodell                  Nachweis
 ┌───────────────────┐        ┌───────────────────┐        ┌───────────────────┐
 │  STUFE 1          │        │  Projekt (JSON)   │        │  STUFE 2          │
 │  Extraktion       │ ─────▶ │  Räume · Bauteile │ ─────▶ │  DIN-Engine       │
 │  Claude Vision    │        │  Schichten · Rolle│        │  (deterministisch)│
 │  (austauschbar)   │   HITL │  prüfbar/editbar  │        │  Report + Export  │
 └───────────────────┘        └───────────────────┘        └───────────────────┘
```

- **Stufe 1 (KI, austauschbar):** `Plan → Bild → Claude liest per Read-Tool → JSON`. Zwei Modi:
  - **Einzelbild** (`extraction/claude_vision.py`) für saubere Einzel-Pläne / Demo.
  - **Kachel-Pipeline** (`extraction/real_plan.py`) für **echte, dichte Ausführungspläne (A1, 1:50)**:
    Legende separat lesen (Schraffur→Material) → Plan in hochauflösende, überlappende Kacheln zerlegen →
    je Kachel Räume + Wände + Wohnungen (WHG) → Schnitt für Deckenaufbau → dedupliziert mergen.
  - Fällt KI aus, lädt man ein vor-extrahiertes Modell-JSON — die Demo fällt nie hart aus.
- **Stufe 2 (deterministisch, der Kern):** keine LLM-Abhängigkeit, voll reproduzierbar. Hier liegt der Engineering-Wert.
- **Human-in-the-Loop:** der Ingenieur prüft/korrigiert die extrahierte Tabelle, bevor gerechnet wird.

---

## Normative Basis (im Code umgesetzt)

| Norm | Verwendung |
|---|---|
| **DIN 4109-1:2018** | Anforderungswerte erf. R′w / zul. L′n,w (Tab. 2 MFH, Tab. 3 EFH-Reihenhaus) → `data/requirements.json` |
| **DIN 4109-32:2016** | m′ = d·ρ (Gl. 3); R_w aus Masse (Gl. 13–16); L_n,eq,0,w = 164 − 35·lg(m′) (Gl. 21) → `engine.py` |
| **DIN 4109-2:2018** | eingebaute Werte; **Trittschall-Flankenkorrektur K = 0,6 + 5,5·lg(m′s/m′f,m)** (Gl. 25/26/27) |
| **DIN 4109-34:2016** | Verbesserung ΔR_w (Vorsatzschale) / ΔL_w (schwimmender Estrich) |
| **DIN EN ISO 10456** | Rohdichte-Rechenwerte → `data/materials.json` |

Fachlich korrekt umgesetzt u. a.: Massekurven je Material (Beton/KS/Ziegel/Leichtbeton/Porenbeton),
Ausschluss der Masse des **schwimmenden Estrichs** aus der Rohdecke (DIN 4109-32 §4.8.4.2) mit
Erfassung als ΔL_w, **massenabhängige Trittschall-Flankenkorrektur nach DIN 4109-2 Gl. 26**
(mittlere Flankenmasse m′f,m automatisch aus den Modell-Wänden), Tür-Anforderung auf R_w statt R′w.

**Validierungs-/Referenz:** [KS-Schallschutzrechner](https://www.ks-schallschutzrechner.de/) (Kalksandstein-Industrie)
rechnet das volle EN-12354-Flankenmodell (4 Wege Dd/Ff/Fd/Df) — geeignet zum Abgleich unserer R′w-Werte.

---

## Quickstart

```powershell
# venv mit allen Paketen liegt bereits unter agenticAi\.venv
$py = "C:\Users\kschu\Downloads\agenticAi\agenticAi\.venv\Scripts\python.exe"

# 1. Demo-Plan erzeugen (optional, liegt schon in examples/)
& $py examples\generate_synthetic_plan.py

# 2a. Streamlit-Demo (UI)
& $py -m streamlit run app.py

# 2b. ODER End-to-End per CLI (Plan -> Nachweis -> Report)
& $py demo_pipeline.py examples\plan_demo.png

# 2c. ODER nur die Engine auf einem Modell-JSON
& $py run_nachweis.py examples\example_model.json
```

UI: **localhost:8501** → Tab 1 Plan extrahieren → Tab 2 prüfen → Tab 3 Nachweis + Download.

> Claude Vision läuft über das **Max-Abo** (Claude Agent SDK, kein API-Key) — Auth via lokale Claude-Code-Session.

---

## Projektstruktur

```
hackathonLösung/
├── app.py                      # Streamlit-Demo (3 Tabs: Extraktion · Modell · Nachweis)
├── demo_pipeline.py            # CLI End-to-End: Plan -> Vision -> Nachweis -> Report
├── run_nachweis.py             # CLI: Modell-JSON -> Nachweis-Tabelle
├── data/
│   ├── requirements.json       # DIN 4109-1 Anforderungen (Tab. 2/3)
│   └── materials.json          # Rohdichten + Massekurven-Kategorie
├── src/schallschutz/
│   ├── models.py               # Zwischenmodell (Pydantic): Projekt/Raum/Bauteil/Schicht
│   ├── knowledge.py            # lädt Wissensbasis (JSON)
│   ├── engine.py               # DIN-Formeln: m', R_w, R'w, L'n,w
│   ├── nachweis.py             # Abgleich vorhanden vs. erforderlich -> Ampel
│   ├── report.py               # HTML-Nachweis-Report
│   ├── export.py               # Excel/JSON-Export (Software-Eingabe)
│   └── extraction/             # STUFE 1: Plan -> Modell (Claude Vision)
│       ├── claude_vision.py    #   PDF->PNG, SDK-Call, JSON-Parsing
│       └── schema.py           #   Extraktions-Prompt + erlaubte Werte
├── examples/                   # synthetischer Demo-Plan + Beispielmodelle
└── outputs/                    # generierte Reports/Exports
```

---

## Grenzen (PoC, bewusst)

- **Luftschall-Flankenübertragung** vereinfacht (Pauschalkorrektur R′w = R_w − K). Das volle
  EN-12354-4-Wege-Modell (Dd/Ff/Fd/Df) nach DIN 4109-2, 4.2.2 = Ausbaustufe (siehe KS-Rechner).
  *(Trittschall-Flanken sind dagegen norm-korrekt nach Gl. 26 umgesetzt.)*
- Bauteilkatalog auf gängige Massivbauteile fokussiert (Holz-/Trockenbau -33 nicht enthalten).
- Ersetzt **keinen** geprüften bauakustischen Nachweis — Entscheidungsunterstützung für Ingenieure.
