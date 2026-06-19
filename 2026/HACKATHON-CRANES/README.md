# HACKATHON-CRANES

Tower crane positioning optimizer for construction sites, built from an IFC building model.

Given BIM geometry and a crane load chart (WOLFF 7534.16 clear), the tool estimates lift weights, visualizes where heavy elements cluster, and recommends mast positions that maximize reachable load while respecting capacity limits.

## Team
Svetlana Gorovaia svetlana.gorovaia@study.thws.de
Damian Jeyakumar damian.jeyakumar@study.thws.de
RuiSheng He ruisheng.he@study.thws.de
 

## Project layout

```
HACKATHON-CRANES/
├── data/                  # inputs & derived tables
│   ├── crane_config.json  # WOLFF 7534.16 load charts
│   ├── ifc_elements.csv
│   ├── element_weights.csv
│   ├── beams_table.csv
│   └── input/             # IFC / RVT (local only, not in git)
├── plots/                 # generated images
├── pipeline/              # Python scripts
├── requirements.txt
└── README.md
```

## Problem

On site, the crane must reach heavy precast elements — especially **stairs**, **beams**, and **columns** — without exceeding the load chart at each outreach. Standing too far from a stair core means the lift is impossible or requires a larger crane.

This project turns the IFC model into actionable placement guidance.

## Pipeline

```
data/input/*.ifc  →  pipeline/ifc_to_csv.py
                      pipeline/ifc_element_weights.py
                              ↓
                         data/*.csv
                              ↓
                 pipeline/plot_load_heatmap.py   (where is load heavy?)
                              ↓
                 pipeline/geometric_visualizer.py   (where should masts go?)
                              ↓
                         plots/*.png
```

| Script | Purpose |
|--------|---------|
| `pipeline/ifc_to_csv.py` | Export element positions and dimensions from IFC |
| `pipeline/ifc_to_2d_plan.py` | 2D floor-plan PNG from IFC |
| `pipeline/ifc_element_weights.py` | Mesh-based lift weights (more accurate than bounding boxes) |
| `pipeline/ifc_beams_table.py` | Beam section sizes and weights |
| `pipeline/plot_2d_scheme.py` | 2D scheme from `data/ifc_elements.csv` |
| `pipeline/plot_load_heatmap.py` | **Load heat map** — hot zones need the crane closer |
| `pipeline/geometric_visualizer.py` | **Crane mast placement** with capacity-chart scoring |

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Pre-generated CSVs in data/ — run visualizations directly:
python -m pipeline.plot_load_heatmap
python -m pipeline.geometric_visualizer --top 3
```

To regenerate data from the IFC file (not included in this repo due to size):

```bash
# Place IFC in data/input/
python -m pipeline.ifc_to_csv
python -m pipeline.ifc_element_weights
python -m pipeline.ifc_to_2d_plan
```

Set `MPLCONFIGDIR=./.mplconfig` if matplotlib cannot write to the default cache directory.

## Crane configuration

`data/crane_config.json` contains the **WOLFF 7534.16 clear** load tables (2-strand and 4-strand reeving), digitized from the manufacturer handbook. Capacity is interpolated by jib length and outreach.

## Sample outputs (`plots/`)

| File | Description |
|------|-------------|
| `2d_plan.png` | Building footprint from IFC |
| `load_heatmap.png` | Lift-load density (stairs, beams, columns) |
| `load_heatmap_1 crane.png` | Heat map with single-crane overlay |
| `crane_positions.png` | Recommended mast positions (from `geometric_visualizer`) |

## Input data (local only)

These files go in `data/input/` and are **not** committed (too large for Git hosting):

| File | Size | Notes |
|------|------|-------|
| `RB_Kran Opt(HACKATHON).ifc` | ~123 MB | Revit-exported building model |
| `RB_Kran Opt(HACKATHON).0001.rvt` | ~531 MB | Source Revit file |
| `Betriebshandbuch WK 7534.16/` | ~73 MB | Crane manufacturer PDFs (reference, project root) |

Derived CSVs in `data/` are committed so the analysis can be reproduced without the IFC.

## Key ideas

1. **Heat map** — Gaussian-smoothed kg/m² of crane-lifted elements; stair cores and beam lines show as hot zones.
2. **Weight estimation** — mesh volume from IfcOpenShell geometry, with material densities where IFC has no mass properties.
3. **Placement scoring** — grid search outside the building footprint; score = sum of liftable element weight within radius and capacity chart.
4. **Fleet planning** — greedy multi-crane assignment to cover remaining uncovered elements.

## Requirements

- Python 3.10+
- ifcopenshell, matplotlib, numpy, pandas, scipy

## Hackathon

Built during a hackathon to automate tower crane siting from BIM data, replacing manual guesswork with geometry-aware, capacity-constrained optimization.
