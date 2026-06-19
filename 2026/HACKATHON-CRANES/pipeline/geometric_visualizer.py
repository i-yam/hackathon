#!/usr/bin/env python3
"""
Predict the best crane installation positions based on a crane model config
and the building element data from the IFC.

Scoring logic
─────────────
For each candidate position outside the building footprint, compute a
"lift-score" = sum of estimated element weights that fall within the
crane's working radius AND are within its max-load capacity at that distance.

The position with the highest lift-score is the best: it can reach the most
construction material without the crane needing to reposition.

Inputs
──────
  --crane-config  JSON file describing the crane model (default: data/crane_config.json)
  --csv           IFC elements CSV (default: data/ifc_elements.csv)

Run
───
  python -m pipeline.geometric_visualizer
  python -m pipeline.geometric_visualizer --crane-config my_crane.json --top 5
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull

from .element_weights import DEFAULT_WEIGHTS_TABLE, element_weight_kg, is_lift_element, lift_element_mask, load_element_weights
from .paths import CRANE_CONFIG, CRANE_POSITIONS_PNG, IFC_ELEMENTS_CSV, PLAN_2D_PNG

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CSV_PATH    = IFC_ELEMENTS_CSV
CONFIG_PATH = CRANE_CONFIG
IMAGE_PATH  = PLAN_2D_PNG
OUTPUT_PATH = CRANE_POSITIONS_PNG

# Image coordinate extents (matches ifc_to_2d_plan.py: CSV range + 5 m pad)
IMG_XLIM = (-5.0, 142.0)
IMG_YLIM = (-20.0, 49.0)

# Material densities  kg/m³
DENSITY = {
    "concrete":    2400,
    "steel":       7850,
    "masonry":     1800,
    "insulation":   50,
    "default":     2000,
}

# Approximate floor-to-floor height for elements without explicit z-span  m
FLOOR_HEIGHT = 4.0

# Minimum clearance from building envelope before placing crane mast  m
CLEARANCE = 5.0

# Grid resolution for candidate search  m
GRID_STEP = 5.0

# Extra margin added to tightest geometric reach  m
RADIUS_MARGIN = 2.0

# Joint fleet optimisation (interactive mode only)
CANDIDATE_TOP_K = 45
EXACT_COMBO_MAX_N = 4

# Prefer masts near stairs / beams / columns (heat-map hot zones)
LIFT_PRIORITY: dict[str, float] = {
    "IfcStair": 3.0,
    "IfcBeam": 2.5,
    "IfcColumn": 1.5,
}

# IFC model positions (shown as reference only)
IFC_TOWER_POS  = (39.26, 34.37)
IFC_MOBILE_POS = (31.15, 43.96)


# ---------------------------------------------------------------------------
# Crane config loader
# ---------------------------------------------------------------------------

def _capacity_curve_from_row(jib_row: dict) -> list[tuple[float, float]]:
    return sorted((float(r), float(t)) for r, t in jib_row["capacity_t"].items())


def _interp_capacity(curve: list[tuple[float, float]], dist_m: float) -> float:
    if not curve:
        return 0.0
    if dist_m <= curve[0][0]:
        return curve[0][1]
    if dist_m >= curve[-1][0]:
        return curve[-1][1]
    for (r0, c0), (r1, c1) in zip(curve, curve[1:]):
        if r0 <= dist_m <= r1:
            if r1 == r0:
                return c0
            t = (dist_m - r0) / (r1 - r0)
            return c0 + t * (c1 - c0)
    return curve[-1][1]


def _normalize_wolff_config(cfg: dict, configuration: str | None, jib_length_m: float | None) -> dict:
    configs = cfg.get("configurations")
    if not configs:
        raise ValueError("crane_config.json has no 'configurations' block")

    if configuration is None:
        configuration = "4_strang" if "4_strang" in configs else next(iter(configs))
    if configuration not in configs:
        available = ", ".join(sorted(configs))
        raise ValueError(f"Unknown configuration '{configuration}'. Available: {available}")

    sub = configs[configuration]
    load_table = sub.get("load_table", [])
    if not load_table:
        raise ValueError(f"Configuration '{configuration}' has an empty load_table")

    if jib_length_m is None:
        jib_length_m = float(
            cfg.get("default_jib_length_m")
            or cfg.get("reference_hook_path_m")
            or cfg.get("max_jib_length_m")
            or max(r["jib_length_m"] for r in load_table)
        )

    jib_row = min(load_table, key=lambda r: abs(float(r["jib_length_m"]) - jib_length_m))
    return _crane_from_jib_row(cfg, configuration, jib_row)


def _crane_from_jib_row(cfg: dict, configuration: str, jib_row: dict) -> dict:
    """Build a crane dict for one load-table jib row."""
    sub = cfg["configurations"][configuration]
    load_table = sub.get("load_table", [])
    curve = _capacity_curve_from_row(jib_row)
    chart_max_outreach_m = curve[-1][0]
    tip_load = curve[-1][1]
    model = cfg.get("model", "crane")
    jib_m = float(jib_row["jib_length_m"])
    return {
        "model": f"{model} ({configuration}, jib {jib_m:.0f} m)",
        "manufacturer": cfg.get("manufacturer", ""),
        "configuration": configuration,
        "jib_length_m": jib_m,
        "max_jib_length_m": float(cfg.get("max_jib_length_m", jib_m)),
        "radius_m": chart_max_outreach_m,
        "chart_max_outreach_m": chart_max_outreach_m,
        "max_load_t": float(sub.get("max_load_t", curve[0][1])),
        "max_load_at_tip_t": tip_load,
        "capacity_curve": curve,
        "load_table": load_table,
        "rope_weight_reduction_kg_per_m": float(sub.get("rope_weight_reduction_kg_per_m", 0)),
        # Exact load-table row from crane_config.json (for reporting).
        "jib_row": dict(jib_row),
        "config_path_key": f"configurations.{configuration}.load_table[jib_length_m={jib_m:g}]",
    }


def format_crane_config_block(crane: dict) -> str:
    """Print the crane_config.json row that was selected (not site-planning numbers)."""
    row = crane.get("jib_row") or {}
    cfg_name = crane.get("configuration", "?")
    catalog_jib = float(crane.get("max_jib_length_m", crane["jib_length_m"]))
    lines = [
        f"Selected crane (crane_config.json → configurations.{cfg_name}):",
        f"  model              : {crane.get('model', '').split(' (')[0]}",
        f"  reeving            : {cfg_name}",
        f"  jib_length_m       : {row.get('jib_length_m', crane['jib_length_m'])} m  "
        f"(catalog allows up to {catalog_jib:g} m)",
        f"  max_load_t         : {crane['max_load_t']:.1f} t",
        f"  max_load_radius    : {row.get('max_load_radius_min_m', '?')} – "
        f"{row.get('max_load_radius_max_m', '?')} m",
    ]
    cap = row.get("capacity_t") or {}
    if cap:
        chart = "  ".join(f"{float(r):g} m → {float(t):g} t" for r, t in sorted(cap.items(), key=lambda x: float(x[0])))
        lines.append(f"  capacity_t         : {chart}")
    return "\n".join(lines)


def format_crane_summary(crane: dict) -> str:
    """One-line crane config reference."""
    row = crane.get("jib_row") or {}
    return (
        f"{crane.get('model', 'crane')}  "
        f"[{crane.get('config_path_key', 'crane_config.json')}]"
    )


def format_mast_line(pos: dict, crane: dict | None = None) -> str:
    """Planned mast on the site plan — separate from the crane catalog row."""
    rank = f"C{pos.get('crane_id', '?')}"
    furthest = pos["radius_m"] - RADIUS_MARGIN
    chart_max = float(crane["chart_max_outreach_m"]) if crane else None
    reach = f"furthest assigned lift at {furthest:.1f} m hook radius"
    if chart_max is not None:
        reach += f" (chart for this jib goes to {chart_max:g} m)"
    return (
        f"  {rank}  mast on site plan ({pos['x']:.1f}, {pos['y']:.1f}) m  ·  "
        f"{reach}  ·  {pos.get('covered_count', '?')} lifts"
    )


def _read_crane_config(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def iter_jib_cranes(
    cfg: dict,
    configuration: str | None = None,
    *,
    ascending: bool = True,
) -> list[dict]:
    """All jib options from the load table, sorted by jib length."""
    configs = cfg.get("configurations")
    if not configs:
        return []
    if configuration is None:
        configuration = "4_strang" if "4_strang" in configs else next(iter(configs))
    rows = sorted(
        configs[configuration]["load_table"],
        key=lambda r: float(r["jib_length_m"]),
        reverse=not ascending,
    )
    return [_crane_from_jib_row(cfg, configuration, row) for row in rows]


def select_optimal_jib(
    footprint: np.ndarray,
    df: pd.DataFrame,
    weights: pd.Series,
    cfg: dict,
    configuration: str | None = None,
    max_cranes: int = 3,
    extra_lift_types: set[str] | None = None,
) -> tuple[dict, list[dict], set, pd.DataFrame, str]:
    """
    Pick the shortest jib from the load table that covers all lifts with <= max_cranes.

    Scans jib rows shortest-first (better capacity at short outreach). Falls back to the
    jib with fewest uncovered lifts if none achieves full coverage.

    Returns (crane, positions, uncovered, uncovered_df, selection_note).
    """
    cranes = iter_jib_cranes(cfg, configuration, ascending=True)
    if not cranes:
        raise ValueError("No jib options in crane configuration")

    task_mask = _lift_task_mask(df, weights, extra_types=extra_lift_types)
    n_tasks = int(task_mask.sum())
    active_weights = weights[task_mask]
    heaviest = float(active_weights.max()) if n_tasks else 0.0

    best_partial: tuple | None = None
    best_partial_key: tuple | None = None

    for crane in cranes:
        peak_cap = crane["capacity_curve"][0][1] if crane.get("capacity_curve") else 0.0
        if heaviest > peak_cap + 1e-6:
            continue

        positions, uncovered, uncovered_df = plan_crane_fleet(
            footprint, df, weights, crane, max_cranes=max_cranes, extra_lift_types=extra_lift_types,
        )
        n_unc = len(uncovered)
        if n_tasks and n_unc == 0:
            note = (
                f"auto-selected shortest jib ({crane['jib_length_m']:.0f} m) — "
                f"full coverage with {len(positions)} crane(s)"
            )
            return crane, positions, uncovered, uncovered_df, note

        missed_t = float(weights.loc[list(uncovered)].sum()) if uncovered else 0.0
        key = (-n_unc, -missed_t, len(positions), -crane["jib_length_m"])
        if best_partial_key is None or key > best_partial_key:
            best_partial_key = key
            best_partial = (crane, positions, uncovered, uncovered_df)

    if best_partial is not None:
        crane, positions, uncovered, uncovered_df = best_partial
        n_unc = len(uncovered)
        note = (
            f"auto-selected jib {crane['jib_length_m']:.0f} m — "
            f"{n_tasks - n_unc}/{n_tasks} lifts with {len(positions)} crane(s)"
        )
        if n_unc:
            note += f", {n_unc} still uncovered (try more cranes or longer jib)"
        return crane, positions, uncovered, uncovered_df, note

    crane = cranes[-1]
    positions, uncovered, uncovered_df = plan_crane_fleet(
        footprint, df, weights, crane, max_cranes=max_cranes, extra_lift_types=extra_lift_types,
    )
    note = f"fallback longest jib {crane['jib_length_m']:.0f} m (heaviest lift {heaviest:.1f} t)"
    return crane, positions, uncovered, uncovered_df, note


def resolve_crane_and_fleet(
    path: Path,
    footprint: np.ndarray,
    df: pd.DataFrame,
    weights: pd.Series,
    *,
    configuration: str | None = None,
    jib_length_m: float | None = None,
    max_cranes: int = 3,
    extra_lift_types: set[str] | None = None,
) -> tuple[dict, list[dict], set, pd.DataFrame, str | None]:
    """
    Load crane + plan fleet. jib_length_m=None → auto-select from load table.
    Returns selection_note when jib was auto-selected.
    """
    cfg = _read_crane_config(path)
    if "configurations" not in cfg:
        crane = load_crane(path, configuration=configuration, jib_length_m=jib_length_m)
        positions, uncovered, uncovered_df = plan_crane_fleet(
            footprint, df, weights, crane, max_cranes=max_cranes, extra_lift_types=extra_lift_types,
        )
        return crane, positions, uncovered, uncovered_df, None

    if jib_length_m is not None:
        crane = _normalize_wolff_config(cfg, configuration, jib_length_m)
        positions, uncovered, uncovered_df = plan_crane_fleet(
            footprint, df, weights, crane, max_cranes=max_cranes, extra_lift_types=extra_lift_types,
        )
        return crane, positions, uncovered, uncovered_df, None

    crane, positions, uncovered, uncovered_df, note = select_optimal_jib(
        footprint, df, weights, cfg, configuration, max_cranes, extra_lift_types,
    )
    return crane, positions, uncovered, uncovered_df, note


def load_crane(
    path: Path,
    configuration: str | None = None,
    jib_length_m: float | None = None,
) -> dict:
    with open(path) as f:
        cfg = json.load(f)

    if "configurations" in cfg:
        return _normalize_wolff_config(cfg, configuration, jib_length_m)

    required = {"model", "radius_m", "max_load_t", "max_load_at_tip_t"}
    missing = required - cfg.keys()
    if missing:
        raise ValueError(f"crane_config.json is missing keys: {missing}")
    return cfg


def load_at_radius(crane: dict, dist_m: float) -> float:
    """Max lift capacity [t] at hook radius dist_m."""
    curve = crane.get("capacity_curve")
    if curve:
        return _interp_capacity(curve, dist_m)

    r = crane["radius_m"]
    inner_r = 0.25 * r
    if dist_m <= inner_r:
        return crane["max_load_t"]
    if dist_m >= r:
        return crane["max_load_at_tip_t"]
    t = (dist_m - inner_r) / (r - inner_r)
    return crane["max_load_t"] + t * (crane["max_load_at_tip_t"] - crane["max_load_t"])


# ---------------------------------------------------------------------------
# Element weight estimation from CSV data
# ---------------------------------------------------------------------------

def _material_density(mat: str) -> float:
    m = str(mat).lower()
    if "beton" in m or "concrete" in m or "fertigteil" in m:
        return DENSITY["concrete"]
    if "stahl" in m or "steel" in m or "metall" in m:
        return DENSITY["steel"]
    if "mauerwerk" in m or "kalksandstein" in m or "masonry" in m:
        return DENSITY["masonry"]
    if "dämm" in m or "insul" in m:
        return DENSITY["insulation"]
    return DENSITY["default"]


def _parse_cross_section(name: str) -> tuple[float, float] | None:
    """Extract (dim_a_mm, dim_b_mm) from strings like '400 x 1600'."""
    m = re.search(r"(\d{2,4})\s*x\s*(\d{2,4})", str(name))
    if m:
        return float(m.group(1)) / 1000, float(m.group(2)) / 1000
    return None


def estimate_weights(
    df: pd.DataFrame,
    weights_table: str | Path = DEFAULT_WEIGHTS_TABLE,
    extra_lift_types: set[str] | None = None,
) -> pd.Series:
    """Return lift weights in tonnes (0 for non-lift elements)."""
    by_gid = load_element_weights(weights_table)
    weights = []
    for _, row in df.iterrows():
        if not is_lift_element(row, extra_types=extra_lift_types):
            weights.append(0.0)
            continue
        kg = element_weight_kg(row, by_gid)
        weights.append((kg or 0.0) / 1000.0)
    return pd.Series(weights, index=df.index, name="lift_weight_t")


# ---------------------------------------------------------------------------
# Building footprint
# ---------------------------------------------------------------------------

def building_footprint(df: pd.DataFrame) -> np.ndarray:
    struct = df[df["ifc_type"].isin({
        "IfcWall", "IfcWallStandardCase", "IfcColumn", "IfcSlab",
    })][["x_m", "y_m"]].dropna().values
    hull = ConvexHull(struct)
    return struct[hull.vertices]


def dilate(fp: np.ndarray, margin: float) -> np.ndarray:
    c = fp.mean(axis=0)
    d = np.linalg.norm(fp - c, axis=1, keepdims=True).clip(min=1e-9)
    return c + (fp - c) * (1 + margin / d)


def in_polygon(px: float, py: float, poly: np.ndarray) -> bool:
    n, inside, j = len(poly), False, len(poly) - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------------
# Placement scoring
# ---------------------------------------------------------------------------

def coverage_points(df: pd.DataFrame, weights: pd.Series, footprint: np.ndarray) -> np.ndarray:
    """XY points the crane jib must reach: lift elements + building envelope."""
    lift = df.loc[weights > 0, ["x_m", "y_m"]].values
    if footprint is not None and len(footprint) >= 3:
        return np.vstack([lift, footprint]) if len(lift) else footprint.copy()
    return lift


def min_coverage_radius(cx: float, cy: float, points: np.ndarray, margin: float = RADIUS_MARGIN) -> float:
    """Smallest jib radius that reaches every coverage point from (cx, cy)."""
    if len(points) == 0:
        return 0.0
    dists = np.sqrt((points[:, 0] - cx) ** 2 + (points[:, 1] - cy) ** 2)
    return float(dists.max()) + margin


def can_lift_at(crane: dict, dist_m: float, weight_t: float) -> bool:
    """True if crane capacity at hook radius dist_m covers the load."""
    if weight_t <= 0 or dist_m > crane["radius_m"]:
        return False
    return load_at_radius(crane, dist_m) >= weight_t


def min_radius_for_load(crane: dict, weight_t: float) -> float | None:
    """Shortest outreach [m] where the crane can lift weight_t (None = impossible)."""
    for radius, capacity in crane.get("capacity_curve", []):
        if capacity >= weight_t:
            return radius
    return None


def max_radius_for_load(crane: dict, weight_t: float) -> float | None:
    """Longest outreach [m] where interpolated chart capacity still covers weight_t."""
    curve = crane.get("capacity_curve") or []
    if not curve or weight_t <= 0:
        return None
    r_min = float(curve[0][0])
    r_max = float(crane["radius_m"])
    if not can_lift_at(crane, r_min, weight_t):
        return None
    if can_lift_at(crane, r_max, weight_t):
        return r_max
    lo, hi = r_min, r_max
    for _ in range(48):
        mid = (lo + hi) / 2
        if can_lift_at(crane, mid, weight_t):
            lo = mid
        else:
            hi = mid
    return lo


def radius_at_capacity(crane: dict, capacity_t: float) -> float | None:
    """Hook radius [m] where chart capacity equals capacity_t (iso-capacity boundary)."""
    curve = crane.get("capacity_curve") or []
    if not curve or capacity_t <= 0:
        return None
    if capacity_t >= curve[0][1]:
        return curve[0][0]
    if capacity_t <= curve[-1][1]:
        return curve[-1][0]
    for (r0, c0), (r1, c1) in zip(curve, curve[1:]):
        if c0 >= capacity_t >= c1:
            if c1 == c0:
                return r1
            t = (capacity_t - c0) / (c1 - c0)
            return r0 + t * (r1 - r0)
    return None


def capacity_ring_points(
    crane: dict,
    limit_m: float | None = None,
    max_rings: int = 10,
) -> list[tuple[float, float]]:
    """
    (outreach_m, capacity_t) pairs from the load chart for iso-radius drawing.

    Generic over any crane dict with ``capacity_curve`` (WOLFF load_table or legacy).
    Decimates dense charts so plots stay readable.
    """
    curve = crane.get("capacity_curve") or []
    if not curve:
        return []
    limit = limit_m if limit_m is not None else float(crane["radius_m"])
    pts = [(float(r), float(c)) for r, c in curve if r <= limit + 0.01]
    if not pts:
        return []
    if max_rings <= 0 or len(pts) <= max_rings:
        return pts
    idx = np.linspace(0, len(pts) - 1, max_rings, dtype=int)
    return [pts[i] for i in sorted(set(idx.tolist()))]


def suggested_capacity_levels(crane: dict, n: int = 5) -> list[float]:
    """Pick n distinct tonnage levels from the chart for iso-capacity rings."""
    caps = sorted({round(c, 1) for _, c in crane.get("capacity_curve", [])}, reverse=True)
    if not caps:
        return []
    if len(caps) <= n:
        return caps
    idx = np.linspace(0, len(caps) - 1, n, dtype=int)
    return [caps[i] for i in sorted(set(idx.tolist()), reverse=True)]


def draw_capacity_iso_radii(
    ax,
    cx: float,
    cy: float,
    crane: dict,
    color: str,
    *,
    limit_m: float | None = None,
    max_rings: int = 10,
    label_angle_deg: float = 32.0,
    zorder: int = 7,
    artists: list | None = None,
) -> None:
    """Concentric iso-radius rings: outreach from load chart, labelled with max capacity [t]."""
    rings = capacity_ring_points(crane, limit_m=limit_m, max_rings=max_rings)
    if not rings:
        return

    angle = np.deg2rad(label_angle_deg)
    cos_a, sin_a = float(np.cos(angle)), float(np.sin(angle))

    for radius_m, cap_t in rings:
        patch = plt.Circle(
            (cx, cy),
            radius_m,
            fill=False,
            color=color,
            lw=0.65,
            linestyle="-",
            alpha=0.4,
            zorder=zorder,
        )
        ax.add_patch(patch)
        if artists is not None:
            artists.append(patch)
        line = ax.plot(
            [cx, cx + radius_m * cos_a],
            [cy, cy + radius_m * sin_a],
            color=color,
            lw=0.5,
            alpha=0.35,
            zorder=zorder,
        )
        if artists is not None:
            artists.extend(line)
        label_r = radius_m + max(1.5, radius_m * 0.03)
        ann = ax.annotate(
            f"{radius_m:g} m · {cap_t:g} t",
            xy=(cx + radius_m * cos_a, cy + radius_m * sin_a),
            xytext=(cx + label_r * cos_a, cy + label_r * sin_a),
            fontsize=5.5,
            color=color,
            alpha=0.9,
            ha="left",
            va="center",
            arrowprops=dict(arrowstyle="-", color=color, lw=0.35, alpha=0.35),
            zorder=zorder + 1,
        )
        if artists is not None:
            artists.append(ann)


def draw_capacity_iso_contours(
    ax,
    cx: float,
    cy: float,
    crane: dict,
    color: str,
    *,
    capacity_levels_t: list[float] | None = None,
    limit_m: float | None = None,
    zorder: int = 7,
    artists: list | None = None,
) -> None:
    """
    Iso-capacity rings: largest hook radius where the chart still allows each tonnage.
    Complements iso-radius rings (industry load-diagram zones).
    """
    levels = capacity_levels_t if capacity_levels_t is not None else suggested_capacity_levels(crane)
    limit = limit_m if limit_m is not None else float(crane["radius_m"])
    for cap_t in levels:
        r = radius_at_capacity(crane, cap_t)
        if r is None or r > limit + 0.01:
            continue
        patch = plt.Circle(
            (cx, cy),
            r,
            fill=False,
            color=color,
            lw=0.9,
            linestyle=":",
            alpha=0.55,
            zorder=zorder,
        )
        ax.add_patch(patch)
        if artists is not None:
            artists.append(patch)
        ann = ax.annotate(
            f"≤{cap_t:g} t",
            xy=(cx + r, cy),
            xytext=(cx + r + 2.5, cy + 1.5),
            fontsize=5.5,
            color=color,
            alpha=0.85,
            ha="left",
            zorder=zorder + 1,
        )
        if artists is not None:
            artists.append(ann)


def _lift_task_mask(
    df: pd.DataFrame,
    weights: pd.Series,
    extra_types: set[str] | None = None,
) -> pd.Series:
    mask = weights > 0
    mask &= lift_element_mask(df, extra_types=extra_types)
    return mask


def score_position(
    cx: float,
    cy: float,
    ex: np.ndarray,
    ey: np.ndarray,
    weights: np.ndarray,
    crane: dict,
) -> float:
    """Total tonnes fully liftable (chart capacity ≥ weight at hook radius)."""
    score = 0.0
    for i in range(len(weights)):
        w = float(weights[i])
        if w <= 0:
            continue
        d = float(np.hypot(ex[i] - cx, ey[i] - cy))
        if can_lift_at(crane, d, w):
            score += w
    return score


def _lift_priority_t(row: pd.Series, weight_t: float) -> float:
    return weight_t * LIFT_PRIORITY.get(str(row.get("ifc_type", "")), 1.0)


def _position_rank_key(
    covered: set,
    priority_t: float,
    prox_score: float,
    total_w: float,
    radius: float,
) -> tuple:
    """Higher is better — favour hot-zone coverage and short hook distances."""
    return (len(covered), priority_t, prox_score, total_w, -radius)


def _search_best_position(
    footprint: np.ndarray,
    df: pd.DataFrame,
    weights: pd.Series,
    crane: dict,
    candidate_indices: set,
    existing_positions: list[dict] | None = None,
    min_mast_sep_m: float | None = None,
) -> dict | None:
    if not candidate_indices:
        return None

    bx0, bx1 = df["x_m"].min(), df["x_m"].max()
    by0, by1 = df["y_m"].min(), df["y_m"].max()
    diag = float(np.hypot(bx1 - bx0, by1 - by0))
    search_pad = diag * 0.6 + CLEARANCE
    dilated = dilate(footprint, CLEARANCE)
    sep = min_mast_sep_m if min_mast_sep_m is not None else GRID_STEP * 2.5

    sub_df = df.loc[list(candidate_indices)]
    index_list = list(candidate_indices)

    xs = np.arange(bx0 - search_pad, bx1 + search_pad + GRID_STEP, GRID_STEP)
    ys = np.arange(by0 - search_pad, by1 + search_pad + GRID_STEP, GRID_STEP)

    best: dict | None = None
    best_rank: tuple | None = None
    for gx in xs:
        for gy in ys:
            if in_polygon(gx, gy, dilated):
                continue
            if existing_positions:
                too_close = any(
                    float(np.hypot(gx - p["x"], gy - p["y"])) < sep
                    for p in existing_positions
                )
                if too_close:
                    continue
            covered: set = set()
            max_dist = 0.0
            total_w = 0.0
            priority_t = 0.0
            prox_score = 0.0
            for idx in index_list:
                row = sub_df.loc[idx]
                wt = float(weights.loc[idx])
                d = float(np.hypot(row["x_m"] - gx, row["y_m"] - gy))
                if can_lift_at(crane, d, wt):
                    covered.add(idx)
                    max_dist = max(max_dist, d)
                    total_w += wt
                    pw = _lift_priority_t(row, wt)
                    priority_t += pw
                    prox_score += pw / max(d, 2.0)
            if not covered:
                continue
            radius = max_dist + RADIUS_MARGIN
            if radius > crane["radius_m"]:
                continue
            rank = _position_rank_key(covered, priority_t, prox_score, total_w, radius)
            if best is None:
                best = {
                    "x": float(gx),
                    "y": float(gy),
                    "radius_m": radius,
                    "score": total_w,
                    "liftable_weight_t": total_w,
                    "covered_indices": covered,
                    "covered_count": len(covered),
                }
                best_rank = rank
            elif rank > best_rank:
                best = {
                    "x": float(gx),
                    "y": float(gy),
                    "radius_m": radius,
                    "score": total_w,
                    "liftable_weight_t": total_w,
                    "covered_indices": covered,
                    "covered_count": len(covered),
                }
                best_rank = rank
    return best


def _coverage_from_site(
    gx: float,
    gy: float,
    df: pd.DataFrame,
    weights: pd.Series,
    crane: dict,
    task_indices: set,
) -> tuple[set, float, float] | None:
    """Lifts capacity-OK from (gx, gy), working radius, and their total weight."""
    covered: set = set()
    max_dist = 0.0
    total_w = 0.0
    for idx in task_indices:
        row = df.loc[idx]
        wt = float(weights.loc[idx])
        d = float(np.hypot(row["x_m"] - gx, row["y_m"] - gy))
        if can_lift_at(crane, d, wt):
            covered.add(idx)
            max_dist = max(max_dist, d)
            total_w += wt
    if not covered:
        return None
    radius = max_dist + RADIUS_MARGIN
    if radius > crane["radius_m"]:
        return None
    return covered, radius, total_w


def collect_mast_candidates(
    footprint: np.ndarray,
    df: pd.DataFrame,
    weights: pd.Series,
    crane: dict,
    task_indices: set,
    top_k: int = CANDIDATE_TOP_K,
) -> list[dict]:
    """
    Ranked mast sites outside the footprint — each entry has x, y, covered_indices, radius_m.
    Used for joint N-crane optimisation (not sequential greedy).
    """
    if not task_indices:
        return []

    bx0, bx1 = df["x_m"].min(), df["x_m"].max()
    by0, by1 = df["y_m"].min(), df["y_m"].max()
    diag = float(np.hypot(bx1 - bx0, by1 - by0))
    search_pad = diag * 0.6 + CLEARANCE
    dilated = dilate(footprint, CLEARANCE)

    xs = np.arange(bx0 - search_pad, bx1 + search_pad + GRID_STEP, GRID_STEP)
    ys = np.arange(by0 - search_pad, by1 + search_pad + GRID_STEP, GRID_STEP)

    raw: list[dict] = []
    for gx in xs:
        for gy in ys:
            if in_polygon(gx, gy, dilated):
                continue
            cov = _coverage_from_site(gx, gy, df, weights, crane, task_indices)
            if cov is None:
                continue
            covered, radius, total_w = cov
            raw.append({
                "x": float(gx),
                "y": float(gy),
                "radius_m": radius,
                "covered_indices": covered,
                "covered_count": len(covered),
                "liftable_weight_t": total_w,
            })

    if not raw:
        return []

    raw.sort(key=lambda c: (c["covered_count"], c["liftable_weight_t"], -c["radius_m"]), reverse=True)

    # Drop sites almost on top of a better one
    sep = GRID_STEP * 1.5
    kept: list[dict] = []
    for cand in raw:
        if any(
            np.hypot(cand["x"] - k["x"], cand["y"] - k["y"]) < sep
            and k["covered_count"] >= cand["covered_count"]
            for k in kept
        ):
            continue
        kept.append(cand)
        if len(kept) >= top_k:
            break
    return kept


def _fleet_objective(
    covered: set,
    weights: pd.Series,
    radii: list[float],
    n_lifts: int,
) -> tuple:
    """Higher is better: full cover > count > tonnes > smaller radii."""
    missed = n_lifts - len(covered)
    missed_t = float(weights.sum()) - float(weights.loc[list(covered)].sum()) if covered else float(weights.sum())
    max_r = max(radii) if radii else 0.0
    sum_r = sum(radii)
    return (-missed, len(covered), -missed_t, -max_r, -sum_r)


def _assign_lifts_to_sites(
    sites: list[dict],
    df: pd.DataFrame,
    weights: pd.Series,
    crane: dict,
    task_indices: set,
) -> set:
    """
    Assign each lift to the nearest mast that can lift it; update per-site coverage stats.
    Returns uncovered task indices.
    """
    for s in sites:
        s["covered_indices"] = set()

    for idx in task_indices:
        row = df.loc[idx]
        wt = float(weights.loc[idx])
        best_site = None
        best_dist = float("inf")
        for site in sites:
            d = float(np.hypot(row["x_m"] - site["x"], row["y_m"] - site["y"]))
            if can_lift_at(crane, d, wt) and d < best_dist:
                best_dist = d
                best_site = site
        if best_site is not None:
            best_site["covered_indices"].add(idx)

    uncovered: set = set()
    for idx in task_indices:
        if not any(idx in s["covered_indices"] for s in sites):
            uncovered.add(idx)

    for i, site in enumerate(sites):
        site["crane_id"] = i + 1
        cov = site["covered_indices"]
        site["covered_count"] = len(cov)
        site["liftable_weight_t"] = float(weights.loc[list(cov)].sum()) if cov else 0.0
        site["score"] = site["liftable_weight_t"]
        if cov:
            max_dist = max(
                float(np.hypot(df.loc[j, "x_m"] - site["x"], df.loc[j, "y_m"] - site["y"]))
                for j in cov
            )
            site["radius_m"] = max_dist + RADIUS_MARGIN
        else:
            site["radius_m"] = site.get("radius_m", 0.0)

    return uncovered


def _select_joint_fleet(
    candidates: list[dict],
    n_cranes: int,
    df: pd.DataFrame,
    weights: pd.Series,
    crane: dict,
    task_indices: set,
) -> list[dict]:
    """Pick exactly n_cranes sites jointly maximising covered lifts."""
    if n_cranes <= 0 or not candidates:
        return []

    n_lifts = len(task_indices)
    pool = candidates[: min(len(candidates), 30 if n_cranes > EXACT_COMBO_MAX_N else CANDIDATE_TOP_K)]

    if n_cranes == 1:
        chosen = [pool[0].copy()]
        _assign_lifts_to_sites(chosen, df, weights, crane, task_indices)
        return chosen

    from itertools import combinations

    if n_cranes <= EXACT_COMBO_MAX_N and len(pool) >= n_cranes:
        best_sites: list[dict] | None = None
        best_key: tuple | None = None
        for combo in combinations(range(len(pool)), n_cranes):
            sites = [pool[i].copy() for i in combo]
            _assign_lifts_to_sites(sites, df, weights, crane, task_indices)
            union = set()
            for s in sites:
                union |= s["covered_indices"]
            key = _fleet_objective(union, weights, [s["radius_m"] for s in sites], n_lifts)
            if best_key is None or key > best_key:
                best_key = key
                best_sites = [s.copy() for s in sites]
        if best_sites is not None:
            _assign_lifts_to_sites(best_sites, df, weights, crane, task_indices)
            return best_sites

    # Greedy set cover for larger N: each pick adds most still-uncovered lifts
    selected: list[dict] = []
    uncovered = set(task_indices)
    used_idx: set[int] = set()
    for _ in range(n_cranes):
        best_i = None
        best_gain = -1
        best_key = None
        for i, cand in enumerate(pool):
            if i in used_idx:
                continue
            gain = len(cand["covered_indices"] & uncovered)
            key = (gain, cand["covered_count"], cand["liftable_weight_t"], -cand["radius_m"])
            if gain > best_gain or (gain == best_gain and best_key is not None and key > best_key) or best_i is None:
                best_gain = gain
                best_key = key
                best_i = i
        if best_i is None:
            break
        used_idx.add(best_i)
        selected.append(pool[best_i].copy())
        uncovered -= pool[best_i]["covered_indices"]

    if not selected:
        return []

    _assign_lifts_to_sites(selected, df, weights, crane, task_indices)
    return selected


def _solo_lift_feasible(
    footprint: np.ndarray,
    df: pd.DataFrame,
    weights: pd.Series,
    crane: dict,
    element_idx,
) -> dict | None:
    """Best mast for a single uncovered element (None = no valid position outside footprint)."""
    return _search_best_position(footprint, df, weights, crane, {element_idx})


def plan_crane_fleet(
    footprint: np.ndarray,
    df: pd.DataFrame,
    weights: pd.Series,
    crane: dict,
    max_cranes: int = 3,
    extra_lift_types: set[str] | None = None,
    mast_candidates: list[dict] | None = None,
) -> tuple[list[dict], set, pd.DataFrame]:
    """
    Place up to max_cranes masts (greedy). Each mast is placed near the heaviest
    remaining lifts — stairs and beams weighted highest — with capacity at hook radius.
    """
    task_mask = _lift_task_mask(df, weights, extra_types=extra_lift_types)
    task_indices = set(df.index[task_mask])

    if not task_indices or max_cranes <= 0:
        empty = df.iloc[0:0].copy()
        return [], set(task_indices), empty

    if mast_candidates is not None:
        positions = _select_joint_fleet(
            mast_candidates, max_cranes, df, weights, crane, task_indices,
        )
        uncovered = task_indices - {idx for p in positions for idx in p["covered_indices"]}
    else:
        uncovered = set(task_indices)
        positions: list[dict] = []
        for crane_id in range(max_cranes):
            if not uncovered:
                break
            best = _search_best_position(
                footprint, df, weights, crane, uncovered, existing_positions=positions,
            )
            if best is None or not best["covered_indices"]:
                break
            best["crane_id"] = crane_id + 1
            positions.append(best)
            uncovered -= best["covered_indices"]

    uncovered_df = df.loc[list(uncovered)].copy() if uncovered else df.iloc[0:0].copy()
    if len(uncovered_df):
        uncovered_df["lift_weight_t"] = weights.loc[list(uncovered)].values
        uncovered_df["max_outreach_m"] = uncovered_df["lift_weight_t"].apply(
            lambda w: max_radius_for_load(crane, float(w))
        )

    return positions, uncovered, uncovered_df


def find_best_positions(
    footprint: np.ndarray,
    df: pd.DataFrame,
    weights: pd.Series,
    crane: dict,
    top_n: int,
) -> list[dict]:
    positions, _, _ = plan_crane_fleet(footprint, df, weights, crane, max_cranes=top_n)
    if not positions:
        return []
    min_r = min(p["radius_m"] for p in positions)
    max_score = max(p["score"] for p in positions)
    for p in positions:
        p["score_pct"] = 100 * p["score"] / max_score if max_score > 0 else 0
        p["radius_pct"] = 100 * min_r / p["radius_m"] if p["radius_m"] > 0 else 100
    return positions


# ---------------------------------------------------------------------------
# Elements within reach from a position
# ---------------------------------------------------------------------------

def elements_in_reach(
    cx: float,
    cy: float,
    df: pd.DataFrame,
    weights: pd.Series,
    crane: dict,
    radius_m: float | None = None,
    capacity_checked: bool = True,
) -> pd.DataFrame:
    dists = np.sqrt((df["x_m"] - cx) ** 2 + (df["y_m"] - cy) ** 2)
    r = radius_m if radius_m is not None else crane["radius_m"]
    mask = dists <= r
    if capacity_checked:
        caps = np.array([load_at_radius(crane, d) for d in dists])
        mask &= weights.values <= caps
    sub = df[mask].copy()
    sub["dist_m"] = dists[mask].values
    sub["capacity_t"] = [load_at_radius(crane, d) for d in sub["dist_m"]]
    sub["lift_weight_t"] = weights[mask].values
    return sub.sort_values("lift_weight_t", ascending=False)


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------

POSITION_COLORS = ["#2980b9", "#27ae60", "#8e44ad", "#d35400", "#16a085"]


def draw_crane_overlay(
    ax,
    positions: list[dict],
    crane: dict,
    footprint: np.ndarray | None = None,
    *,
    show_footprint: bool = True,
    annotate: bool = True,
    weights: pd.Series | None = None,
    df: pd.DataFrame | None = None,
    capacity_rings: int = 8,
    iso_capacity: bool = False,
    iso_capacity_levels_t: list[float] | None = None,
    artists: list | None = None,
) -> list:
    """Draw working-radius circles, optional load-chart iso-radii, and mast markers."""
    if artists is None:
        artists = []
    if show_footprint and footprint is not None and len(footprint) >= 3:
        fp = np.vstack([footprint, footprint[0]])
        artists.extend(ax.fill(footprint[:, 0], footprint[:, 1], color="#2c3e50", alpha=0.06, zorder=6))
        artists.extend(ax.plot(fp[:, 0], fp[:, 1], color="#2c3e50", lw=1.2, alpha=0.7, zorder=7))

    r_cfg = crane["radius_m"]
    for i, pos in enumerate(positions):
        color = POSITION_COLORS[i % len(POSITION_COLORS)]
        cx, cy = pos["x"], pos["y"]
        r = pos.get("radius_m", r_cfg)
        label_angle = 28.0 + i * 38.0

        if capacity_rings > 0:
            draw_capacity_iso_radii(
                ax, cx, cy, crane, color,
                limit_m=r,
                max_rings=capacity_rings,
                label_angle_deg=label_angle,
                zorder=7,
                artists=artists,
            )
        if iso_capacity:
            draw_capacity_iso_contours(
                ax, cx, cy, crane, color,
                capacity_levels_t=iso_capacity_levels_t,
                limit_m=r,
                zorder=7,
                artists=artists,
            )

        for patch in (
            plt.Circle((cx, cy), r, color=color, fill=True, alpha=0.08, zorder=8),
            plt.Circle((cx, cy), r, color=color, fill=False, lw=2.0, linestyle="--", alpha=0.95, zorder=9),
        ):
            ax.add_patch(patch)
            artists.append(patch)
        artists.extend(ax.plot(cx, cy, "o", color=color, ms=8, zorder=10))
        artists.extend(ax.plot(cx, cy, "+", color=color, ms=16, mew=2.2, zorder=10))

        if annotate:
            rank = f"C{pos.get('crane_id', i + 1)}"
            label = f"{rank}  ({cx:.0f}, {cy:.0f}) m\nr = {r:.0f} m"
            n_cov = pos.get("covered_count")
            w_cov = pos.get("liftable_weight_t")
            if n_cov is not None:
                label += f"\n{n_cov} lifts · {w_cov:.0f} t"
            elif weights is not None and df is not None:
                reach = elements_in_reach(cx, cy, df, weights, crane, radius_m=r)
                label += f"  ·  {reach['lift_weight_t'].sum():.0f} t"
            ann = ax.annotate(
                label,
                xy=(cx, cy),
                xytext=(cx + 3, cy + r * 0.08 + 3),
                fontsize=7.5,
                color=color,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=color, alpha=0.92, lw=1.0),
                zorder=11,
            )
            artists.append(ann)
    return artists


def plot(
    positions: list[dict],
    footprint: np.ndarray,
    df: pd.DataFrame,
    weights: pd.Series,
    crane: dict,
    output: Path,
    show: bool,
    *,
    capacity_rings: int = 8,
    iso_capacity: bool = False,
    iso_capacity_levels_t: list[float] | None = None,
) -> None:
    _, ax = plt.subplots(figsize=(22, 15))
    ax.set_facecolor("#f7f7f7")

    # Background PNG
    if IMAGE_PATH.exists():
        img = plt.imread(str(IMAGE_PATH))
        ax.imshow(img,
                  extent=[IMG_XLIM[0], IMG_XLIM[1], IMG_YLIM[0], IMG_YLIM[1]],
                  origin="upper", aspect="equal", alpha=0.45, zorder=1)

    # Building footprint
    fp = np.vstack([footprint, footprint[0]])
    ax.fill(footprint[:, 0], footprint[:, 1], color="#2c3e50", alpha=0.08, zorder=2)
    ax.plot(fp[:, 0], fp[:, 1], color="#2c3e50", lw=1.5, zorder=3)

    # All building elements — size proportional to lift weight
    w_arr = weights.values
    sizes = np.clip(w_arr / w_arr.max() * 120, 8, 120)
    type_colors = {
        "IfcColumn": "#c0392b",
        "IfcBeam":   "#e67e22",
        "IfcWall":   "#7f8c8d",
        "IfcWallStandardCase": "#7f8c8d",
        "IfcSlab":   "#3498db",
        "IfcStair":  "#9b59b6",
    }
    for ifc_type, color in type_colors.items():
        sub = df[df["ifc_type"] == ifc_type]
        if len(sub):
            ax.scatter(sub["x_m"], sub["y_m"],
                       s=sizes[sub.index], color=color,
                       alpha=0.5, zorder=4, linewidths=0)

    draw_crane_overlay(
        ax, positions, crane, footprint=None, show_footprint=False,
        weights=weights, df=df,
        capacity_rings=capacity_rings,
        iso_capacity=iso_capacity,
        iso_capacity_levels_t=iso_capacity_levels_t,
    )
    r = crane["radius_m"]

    # IFC model crane position (reference)
    tx, ty = IFC_TOWER_POS
    ax.add_patch(plt.Circle((tx, ty), r,
                             color="#e74c3c", fill=False, lw=2.2,
                             linestyle=":", zorder=10))
    ax.plot(tx, ty, "+", color="#e74c3c", ms=20, mew=3, zorder=11)
    ax.plot(tx, ty, "o", color="#e74c3c", ms=8,  zorder=11)
    ax.annotate(
        f"IFC model position\n{crane['model']}\n({tx:.0f}, {ty:.0f}) m",
        xy=(tx, ty), xytext=(tx + 5, ty + 10),
        fontsize=8, color="#e74c3c", fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", fc="white",
                  ec="#e74c3c", alpha=0.92),
        zorder=12,
    )

    ax.set_xlim(IMG_XLIM[0] - 10, IMG_XLIM[1] + 10)
    ax.set_ylim(IMG_YLIM[0] - 10, IMG_YLIM[1] + r * 0.6)
    ax.set_aspect("equal")
    ax.grid(True, ls="--", lw=0.35, color="#cccccc", zorder=0)
    ax.set_xlabel("X (m)", fontsize=11)
    ax.set_ylabel("Y (m)", fontsize=11)
    ax.set_title(
        f"Best crane installation positions — {crane['model']}  "
        f"|  Radius {r:.0f} m  ·  Max load {crane['max_load_t']:.0f} t\n"
        f"Scored by total liftable construction weight within working radius",
        fontsize=13, fontweight="bold",
    )

    legend_items = [
        mpatches.Patch(color="#2c3e50", alpha=0.5, label="Building footprint"),
        mpatches.Patch(color="#c0392b", alpha=0.6, label="Column (heaviest)"),
        mpatches.Patch(color="#e67e22", alpha=0.6, label="Beam (steel)"),
        mpatches.Patch(color="#7f8c8d", alpha=0.5, label="Wall"),
        mpatches.Patch(color="#3498db", alpha=0.5, label="Slab"),
        mpatches.Patch(color="#e74c3c", alpha=0.5, label="IFC model position"),
    ]
    for i, pos in enumerate(positions):
        color = POSITION_COLORS[i % len(POSITION_COLORS)]
        rank = f"C{pos.get('crane_id', i + 1)}"
        r = pos.get("radius_m", crane["radius_m"])
        legend_items.append(mpatches.Patch(
            color=color, alpha=0.7,
            label=f"{rank}  ({pos['x']:.0f}, {pos['y']:.0f}) m  r={r:.0f} m",
        ))
    if capacity_rings > 0:
        legend_items.append(mpatches.Patch(
            facecolor="none", edgecolor="#555555", linestyle="-",
            label="Iso-radius (outreach · max capacity)",
        ))
    if iso_capacity:
        legend_items.append(mpatches.Patch(
            facecolor="none", edgecolor="#555555", linestyle=":",
            label="Iso-capacity zone",
        ))
    ax.legend(handles=legend_items, loc="lower right",
              fontsize=8, framealpha=0.93,
              title=f"Crane: {crane['model']}", title_fontsize=9)

    plt.tight_layout()
    plt.savefig(str(output), dpi=160, bbox_inches="tight")
    print(f"\nSaved: {output}")

    if show:
        plt.show()


# ---------------------------------------------------------------------------
# Console report
# ---------------------------------------------------------------------------

def print_report(
    positions: list[dict],
    df: pd.DataFrame,
    weights: pd.Series,
    crane: dict,
    uncovered_df: pd.DataFrame | None = None,
) -> None:
    print(f"\n{'═'*60}")
    print(format_crane_config_block(crane))
    print(f" Max load    : {crane['max_load_t']:.0f} t  "
          f"(tip {crane['max_load_at_tip_t']:.1f} t)")
    print(" Rule        : each lift needs capacity ≥ weight at hook radius")
    print(f"{'═'*60}")
    for i, pos in enumerate(positions):
        reach = elements_in_reach(
            pos["x"], pos["y"], df, weights, crane, radius_m=pos.get("radius_m"),
        )
        total = reach["lift_weight_t"].sum()
        print(f"\n{format_mast_line(pos, crane)}")
        print(f"       Liftable (capacity OK) : {total:.1f} t  ({len(reach)} elements)")
        if len(reach):
            for _, el in reach.head(5).iterrows():
                print(
                    f"         • {el['ifc_type']:22s}  {el['lift_weight_t']:5.1f} t  "
                    f"@ {el['dist_m']:.0f} m  (chart {el['capacity_t']:.1f} t)"
                )
    if uncovered_df is not None and len(uncovered_df):
        print(f"\n{'─'*60}")
        print(f" NOT LIFTABLE with {len(positions)} crane(s) — need more cranes or smaller jib loads:")
        for _, el in uncovered_df.sort_values("lift_weight_t", ascending=False).head(10).iterrows():
            w = el["lift_weight_t"]
            rmax = el.get("max_outreach_m")
            hint = ""
            if pd.notna(rmax):
                hint = f"max hook radius {rmax:.0f} m (chart limit for {w:.1f} t)"
            elif w > 0:
                hint = "exceeds chart at all outreach (try shorter jib)"
            print(
                f"         • {el['ifc_type']:22s}  {w:5.1f} t  "
                f"@ ({el['x_m']:.0f}, {el['y_m']:.0f})  {hint}"
            )
    print(f"\n{'═'*60}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--crane-config", default=str(CONFIG_PATH),
                   help="Path to crane model JSON (default: %(default)s)")
    p.add_argument(
        "--reeving",
        default=None,
        help="Crane configuration key, e.g. 2_strang or 4_strang (default: 4_strang if present)",
    )
    p.add_argument(
        "--jib-length",
        type=float,
        default=None,
        help="Jib length in metres (default: auto-select shortest jib from load table)",
    )
    p.add_argument("--csv",          default=str(CSV_PATH),
                   help="Path to IFC elements CSV (default: %(default)s)")
    p.add_argument("--top",          type=int, default=5,
                   help="Max cranes / positions to plan (default: %(default)s)")
    p.add_argument(
        "--capacity-rings",
        type=int,
        default=8,
        help="Iso-radius rings from load chart per crane (0 = off)",
    )
    p.add_argument(
        "--iso-capacity",
        action="store_true",
        help="Draw iso-capacity zones (dotted rings)",
    )
    p.add_argument(
        "--iso-capacity-levels",
        default=None,
        help="Comma-separated tonnage levels for iso-capacity (default: auto)",
    )
    p.add_argument("--output",       default=str(OUTPUT_PATH))
    p.add_argument("--no-show",      action="store_true")
    args = p.parse_args()

    iso_levels = None
    if args.iso_capacity_levels:
        iso_levels = [float(x.strip()) for x in args.iso_capacity_levels.split(",") if x.strip()]

    df         = pd.read_csv(args.csv)
    weights    = estimate_weights(df)
    footprint  = building_footprint(df)

    print(f"Elements     : {len(df)}  |  "
          f"total estimated lift weight {weights.sum():.1f} t")

    crane, positions, uncovered_idx, uncovered_df, jib_note = resolve_crane_and_fleet(
        Path(args.crane_config),
        footprint,
        df,
        weights,
        configuration=args.reeving,
        jib_length_m=args.jib_length,
        max_cranes=args.top,
    )
    print(
        f"Crane loaded : {crane['model']}  r={crane['radius_m']} m  "
        f"max={crane['max_load_t']} t  tip={crane['max_load_at_tip_t']:.1f} t"
    )
    if jib_note:
        print(jib_note)

    if not positions:
        print("No valid positions found — no element liftable within capacity chart.")
        return

    print_report(positions, df, weights, crane, uncovered_df)
    plot(
        positions, footprint, df, weights, crane,
        output=Path(args.output), show=not args.no_show,
        capacity_rings=args.capacity_rings,
        iso_capacity=args.iso_capacity,
        iso_capacity_levels_t=iso_levels,
    )


# make score helper accessible at module level (used inside loop)
load_at_radius = load_at_radius

if __name__ == "__main__":
    main()