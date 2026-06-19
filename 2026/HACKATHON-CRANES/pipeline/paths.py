"""Project paths — data, plots, and pipeline live in separate folders."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PLOTS = ROOT / "plots"
INPUT = DATA / "input"

CRANE_CONFIG = DATA / "crane_config.json"
IFC_ELEMENTS_CSV = DATA / "ifc_elements.csv"
ELEMENT_WEIGHTS_CSV = DATA / "element_weights.csv"
BEAMS_TABLE_CSV = DATA / "beams_table.csv"
DEFAULT_IFC = INPUT / "RB_Kran Opt(HACKATHON).ifc"

PLAN_2D_PNG = PLOTS / "2d_plan.png"
SCHEME_2D_PNG = PLOTS / "2d_scheme.png"
LOAD_HEATMAP_PNG = PLOTS / "load_heatmap.png"
CRANE_POSITIONS_PNG = PLOTS / "crane_positions.png"
