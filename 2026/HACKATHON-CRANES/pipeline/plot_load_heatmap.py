#!/usr/bin/env python3
"""Heat map of lift loads — hotter areas need the crane closer."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

from .element_weights import (
    DEFAULT_WEIGHTS_TABLE,
    element_weight_kg,
    is_lift_element,
    lift_element_mask,
    load_element_weights,
    parse_load_bearing,
)
from .geometric_visualizer import (
    GRID_STEP,
    building_footprint,
    collect_mast_candidates,
    draw_crane_overlay,
    load_crane,
    plan_crane_fleet,
    format_crane_config_block,
    format_crane_summary,
    format_mast_line,
    resolve_crane_and_fleet,
    select_optimal_jib,
    _read_crane_config,
)
from .paths import CRANE_CONFIG, IFC_ELEMENTS_CSV, LOAD_HEATMAP_PNG

CSV_PATH = IFC_ELEMENTS_CSV
OUTPUT_PATH = LOAD_HEATMAP_PNG
CONFIG_PATH = CRANE_CONFIG

HIGHLIGHT_TYPES = {"IfcStair"}
COLUMN_COLOR = "#c00000"
BEAM_COLOR = "#ed7d31"
BEAM_HEAT_WIDTH_M = 2.5  # min plan width for heat (beams are ~0.5 m; blur would erase them)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot crane load heat map from IFC CSV.")
    parser.add_argument("--csv", default=CSV_PATH)
    parser.add_argument("--output", default=OUTPUT_PATH)
    parser.add_argument("--resolution", type=float, default=0.5, help="Grid cell size in metres")
    parser.add_argument(
        "--include-slabs",
        action="store_true",
        help="Include all IfcSlab elements (even when load_bearing is false in IFC)",
    )
    parser.add_argument(
        "--include-walls",
        action="store_true",
        help="Include all wall elements (even when load_bearing is false in IFC)",
    )
    parser.add_argument("--smooth", type=float, default=2.0, help="Gaussian blur sigma in metres")
    parser.add_argument(
        "--beam-heat-width",
        type=float,
        default=BEAM_HEAT_WIDTH_M,
        help="Min plan width (m) for beam heat stripes (beams are thin in IFC)",
    )
    parser.add_argument(
        "--weights-table",
        default=DEFAULT_WEIGHTS_TABLE,
        help="Mesh weights CSV from ifc_element_weights.py",
    )
    parser.add_argument("--beams-table", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--crane-config", default=CONFIG_PATH, help="Crane model JSON for position overlay")
    parser.add_argument(
        "--reeving",
        default=None,
        help="Crane configuration: 2_strang or 4_strang (default: 4_strang)",
    )
    parser.add_argument(
        "--jib-length",
        type=float,
        default=None,
        help="Jib length in metres (default: auto-select shortest jib from load table)",
    )
    parser.add_argument(
        "--top-positions",
        type=int,
        default=3,
        help="Number of cranes to plan and draw (0 = off; default: 3)",
    )
    parser.add_argument(
        "--max-cranes",
        type=int,
        default=5,
        help="Interactive slider maximum — fleet layouts computed for 1..N (default: 5)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Open interactive map — slider to change number of cranes",
    )
    parser.add_argument("--no-crane", action="store_true", help="Skip crane radius overlay")
    parser.add_argument(
        "--capacity-rings",
        type=int,
        default=8,
        help="Iso-radius rings from load chart per crane (0 = off, default 8)",
    )
    parser.add_argument(
        "--iso-capacity",
        action="store_true",
        help="Also draw iso-capacity zones (dotted: max radius for each tonnage level)",
    )
    parser.add_argument(
        "--iso-capacity-levels",
        default=None,
        help="Comma-separated tonnage levels for iso-capacity rings (default: auto from chart)",
    )
    return parser.parse_args()


def lift_extra_types(include_slabs: bool, include_walls: bool) -> set[str]:
    extra: set[str] = set()
    if include_slabs:
        extra.add("IfcSlab")
    if include_walls:
        extra |= {"IfcWall", "IfcWallStandardCase"}
    return extra


def estimate_lift_weight_kg(
    row: pd.Series,
    extra_types: set[str],
    weights_by_gid: dict[str, float] | None = None,
) -> float:
    if not is_lift_element(row, extra_types=extra_types):
        return 0.0

    lookup = element_weight_kg(row, weights_by_gid or {})
    if lookup is not None:
        return lookup

    return 0.0


def prepare_elements_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize ifc_elements.csv — supports full bbox export or centroid-only rows."""
    df = df.copy()
    for col in (
        "length_m", "width_m", "height_m", "rotation_deg",
        "x_m", "y_m", "z_m", "x_min_m", "y_min_m",
    ):
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    has_box = (df["length_m"] > 0.01) & (df["width_m"] > 0.01)
    if has_box.any():
        df.loc[has_box, "x_min_m"] = df.loc[has_box, "x_m"] - df.loc[has_box, "length_m"] / 2
        df.loc[has_box, "y_min_m"] = df.loc[has_box, "y_m"] - df.loc[has_box, "width_m"] / 2

    # Drop duplicate IFC copies at origin (same name, zero position)
    df = df[~((df["x_m"] == 0) & (df["y_m"] == 0) & (df["length_m"] == 0))].copy()
    return df


def rect_corners(row: pd.Series) -> np.ndarray:
    length = float(row.get("length_m", 0) or 0)
    width = float(row.get("width_m", 0) or 0)
    if {"x_min_m", "y_min_m"}.issubset(row.index) and length > 0.05 and width > 0.05:
        x0 = float(row["x_min_m"])
        y0 = float(row["y_min_m"])
        return np.array(
            [
                [x0, y0],
                [x0 + length, y0],
                [x0 + length, y0 + width],
                [x0, y0 + width],
            ]
        )

    cx, cy = float(row["x_m"]), float(row["y_m"])
    if length > 0.01 and width > 0.01:
        angle = np.radians(float(row.get("rotation_deg", 0) or 0))
        local = np.array(
            [
                [-length / 2, -width / 2],
                [length / 2, -width / 2],
                [length / 2, width / 2],
                [-length / 2, width / 2],
            ]
        )
        rot = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        world = local @ rot.T
        world[:, 0] += cx
        world[:, 1] += cy
        return world

    # Centroid-only CSV — draw a small marker square
    half = 0.5 if row.get("ifc_type") == "IfcColumn" else 0.25
    return np.array(
        [
            [cx - half, cy - half],
            [cx + half, cy - half],
            [cx + half, cy + half],
            [cx - half, cy + half],
        ]
    )


def heat_sigmas_m(row: pd.Series, beam_heat_width: float) -> tuple[float, float]:
    """Gaussian spread (σx, σy) in metres for heat splat."""
    ifc_type = row["ifc_type"]
    length = float(row.get("length_m", 0) or 0)
    width = float(row.get("width_m", 0) or 0)

    if ifc_type == "IfcBeam":
        if width >= length:
            return beam_heat_width / 2, max(width / 4, 4.0)
        return max(length / 4, 4.0), beam_heat_width / 2
    if ifc_type == "IfcStair":
        return max(length, 2.0) / 2, max(width, 1.2) / 2
    if ifc_type == "IfcColumn":
        return max(length, 0.4) / 2, max(width, 0.4) / 2
    return max(length, 2.0) / 2, max(width, 2.0) / 2


def splat_weight(
    grid: np.ndarray,
    x_centers: np.ndarray,
    y_centers: np.ndarray,
    cx: float,
    cy: float,
    weight_kg: float,
    sigma_x: float,
    sigma_y: float,
    cell_area: float,
) -> None:
    """Deposit total element weight as a normalized 2D Gaussian (→ kg/m²)."""
    sx = max(sigma_x, 0.3)
    sy = max(sigma_y, 0.3)
    xg, yg = np.meshgrid(x_centers, y_centers)
    kernel = np.exp(-0.5 * ((xg - cx) / sx) ** 2 - 0.5 * ((yg - cy) / sy) ** 2)
    total = kernel.sum()
    if total <= 0 or cell_area <= 0:
        return
    grid += (kernel / total) * weight_kg / cell_area


def build_load_grid(
    df: pd.DataFrame,
    resolution: float,
    smooth_sigma: float,
    extra_lift_types: set[str],
    weights_by_gid: dict[str, float] | None = None,
    beam_heat_width: float = BEAM_HEAT_WIDTH_M,
):
    pad = 8.0
    x_min, x_max = df["x_m"].min() - pad, df["x_m"].max() + pad
    y_min, y_max = df["y_m"].min() - pad, df["y_m"].max() + pad

    x_edges = np.arange(x_min, x_max + resolution, resolution)
    y_edges = np.arange(y_min, y_max + resolution, resolution)
    x_centers = (x_edges[:-1] + x_edges[1:]) / 2
    y_centers = (y_edges[:-1] + y_edges[1:]) / 2
    cell_area = float(resolution * resolution)
    grid = np.zeros((len(y_centers), len(x_centers)), dtype=float)

    df = df.copy()
    df["lift_weight_kg"] = df.apply(
        lambda r: estimate_lift_weight_kg(r, extra_lift_types, weights_by_gid),
        axis=1,
    )

    lift_mask = lift_element_mask(df, extra_types=extra_lift_types)
    lift = df[(df["lift_weight_kg"] > 0) & lift_mask].copy()

    # Stack column segments at the same plan position into one pick weight
    col_mask = lift["ifc_type"] == "IfcColumn"
    if col_mask.any():
        cols = lift[col_mask].copy()
        cols["_gx"] = cols["x_m"].round(2)
        cols["_gy"] = cols["y_m"].round(2)
        merged = (
            cols.groupby(["_gx", "_gy"], as_index=False)
            .agg(
                lift_weight_kg=("lift_weight_kg", "sum"),
                x_m=("x_m", "first"),
                y_m=("y_m", "first"),
                length_m=("length_m", "max"),
                width_m=("width_m", "max"),
                ifc_type=("ifc_type", "first"),
            )
        )
        lift = pd.concat([lift[~col_mask], merged], ignore_index=True)

    for _, row in lift.iterrows():
        if float(row["x_m"]) == 0.0 and float(row["y_m"]) == 0.0:
            continue
        sx, sy = heat_sigmas_m(row, beam_heat_width)
        splat_weight(
            grid,
            x_centers,
            y_centers,
            float(row["x_m"]),
            float(row["y_m"]),
            float(row["lift_weight_kg"]),
            sx,
            sy,
            cell_area,
        )

    if smooth_sigma > 0:
        from scipy.ndimage import gaussian_filter

        sigma_cells = smooth_sigma / resolution
        grid = gaussian_filter(grid, sigma=sigma_cells)

    return grid, x_centers, y_centers, df


def _draw_site_layers(ax, fig, grid, x_centers, y_centers, df: pd.DataFrame):
    """Static heat map + building geometry (no cranes)."""
    ax.set_facecolor("#f0f0f0")
    vmax = np.percentile(grid[grid > 0], 98) if np.any(grid > 0) else 1.0
    display = np.ma.masked_where(grid <= vmax * 0.02, grid)
    cmap = plt.colormaps["OrRd"].copy()
    cmap.set_bad(color="#f0f0f0")
    mesh = ax.pcolormesh(
        x_centers, y_centers, display,
        cmap=cmap, shading="auto", alpha=0.95, vmin=0, vmax=vmax, zorder=1,
    )
    cbar = fig.colorbar(mesh, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Lift load intensity (kg/m², smoothed)", fontsize=10)

    outline_types = ["IfcWall", "IfcWallStandardCase", "IfcSlab"]
    for _, row in df[df["ifc_type"].isin(outline_types)].iterrows():
        if float(row.get("length_m", 0) or 0) < 0.05:
            continue
        if float(row["x_m"]) == 0.0 and float(row["y_m"]) == 0.0:
            continue
        ax.add_patch(mpatches.Polygon(
            rect_corners(row), closed=True, fill=False,
            edgecolor="#666666", linewidth=0.4, alpha=0.5, zorder=2,
        ))

    columns = df[df["ifc_type"] == "IfcColumn"].copy()
    if not columns.empty:
        if (columns["length_m"] > 0.05).any():
            columns = columns[columns["length_m"] > 0.05]
            columns = columns.sort_values("length_m", ascending=False)
        columns = columns.assign(_gx=columns["x_m"].round(2), _gy=columns["y_m"].round(2))
        columns = columns.drop_duplicates(subset=["_gx", "_gy"])
        for _, row in columns.iterrows():
            ax.add_patch(mpatches.Polygon(
                rect_corners(row), closed=True,
                facecolor=COLUMN_COLOR, edgecolor="white", linewidth=0.6, alpha=0.9, zorder=4,
            ))

    beams = df[df["ifc_type"] == "IfcBeam"].copy()
    if not beams.empty and (beams["length_m"] > 0.01).any():
        beams = beams[beams["length_m"] > 0.01]
        for _, row in beams.iterrows():
            ax.add_patch(mpatches.Polygon(
                rect_corners(row), closed=True, facecolor="none",
                edgecolor=BEAM_COLOR, linewidth=1.2, alpha=0.95, zorder=4,
            ))

    for _, row in df[df["ifc_type"].isin(HIGHLIGHT_TYPES)].iterrows():
        if float(row["x_m"]) == 0.0 and float(row["y_m"]) == 0.0:
            continue
        ax.scatter(
            row["x_m"], row["y_m"], s=90, marker="s", color="#6a0dad",
            edgecolors="white", linewidths=0.8, zorder=5,
        )
        ax.annotate(
            f"{row['lift_weight_kg'] / 1000:.0f}t",
            (row["x_m"], row["y_m"]),
            textcoords="offset points", xytext=(6, 6),
            fontsize=8, color="#4a0072", zorder=6,
        )

    footprint = building_footprint(df)
    if len(footprint) >= 3:
        fp = np.vstack([footprint, footprint[0]])
        ax.fill(footprint[:, 0], footprint[:, 1], color="#2c3e50", alpha=0.06, zorder=3)
        ax.plot(fp[:, 0], fp[:, 1], color="#2c3e50", lw=1.0, alpha=0.5, zorder=3)

    ax.set_xlabel("X (m)", fontsize=11)
    ax.set_ylabel("Y (m)", fontsize=11)
    ax.set_aspect("equal")
    ax.grid(True, linestyle="--", linewidth=0.35, color="#bbbbbb", alpha=0.6, zorder=0)
    return footprint


def precache_fleets(
    crane: dict,
    footprint: np.ndarray,
    df: pd.DataFrame,
    weights_t: pd.Series,
    max_cranes: int,
    extra_lift_types: set[str],
) -> dict[int, tuple[list[dict], set, pd.DataFrame]]:
    """Pre-compute joint-optimal fleet layouts for 1..max_cranes."""
    from .element_weights import lift_element_mask

    task_mask = lift_element_mask(df, extra_types=extra_lift_types) & (weights_t > 0)
    task_indices = set(df.index[task_mask])
    candidates = collect_mast_candidates(footprint, df, weights_t, crane, task_indices)

    cache: dict[int, tuple] = {}
    for n in range(1, max_cranes + 1):
        positions, uncovered, uncovered_df = plan_crane_fleet(
            footprint, df, weights_t, crane, max_cranes=n,
            extra_lift_types=extra_lift_types, mast_candidates=candidates,
        )
        cache[n] = (positions, uncovered, uncovered_df)
        print(f"  planned {n}/{max_cranes} ({len(positions)} mast(s))", end="\r", flush=True)
    print()
    return cache


def plot_heatmap_interactive(
    grid,
    x_centers,
    y_centers,
    df: pd.DataFrame,
    crane: dict,
    footprint: np.ndarray,
    weights_t: pd.Series,
    fleet_cache: dict[int, tuple],
    *,
    initial_cranes: int,
    jib_note: str | None,
    capacity_rings: int = 8,
    iso_capacity: bool = False,
    iso_capacity_levels_t: list[float] | None = None,
    output_path: str | None = None,
):
    from matplotlib.widgets import Slider

    n_lift = int((weights_t > 0).sum())
    fig, ax = plt.subplots(figsize=(18, 12))
    plt.subplots_adjust(bottom=0.14)
    footprint = _draw_site_layers(ax, fig, grid, x_centers, y_centers, df)
    status_ax = fig.add_axes([0.15, 0.06, 0.7, 0.04])
    status_ax.axis("off")
    status_text = status_ax.text(0.5, 0.5, "", ha="center", va="center", fontsize=10)

    ax_slider = fig.add_axes([0.15, 0.02, 0.55, 0.03])
    max_slider = max(fleet_cache)
    slider = Slider(
        ax_slider, "Cranes", 1, max_slider,
        valinit=max(1, min(initial_cranes, max_slider)), valstep=1, color="#2980b9",
    )

    title_base = f"Crane load heat map — {crane['model']}"
    if jib_note:
        title_base += f"\n{jib_note}"

    overlay_artists: list = []

    def render(n_cranes: int) -> None:
        nonlocal overlay_artists
        for artist in overlay_artists:
            try:
                artist.remove()
            except ValueError:
                pass
        overlay_artists = []

        positions, uncovered, _ = fleet_cache[int(n_cranes)]
        if positions:
            overlay_artists = draw_crane_overlay(
                ax, positions, crane,
                footprint=None, show_footprint=False,
                annotate=True, weights=weights_t, df=df,
                capacity_rings=capacity_rings,
                iso_capacity=iso_capacity,
                iso_capacity_levels_t=iso_capacity_levels_t,
                artists=overlay_artists,
            )
        covered = n_lift - len(uncovered)
        n_masts = len(positions)
        status = (
            f"{n_masts} mast(s) shown (slider {int(n_cranes)})  ·  "
            f"{covered}/{n_lift} lifts covered  ·  jib {crane['jib_length_m']:.0f} m"
        )
        if uncovered:
            status += f"  ·  {len(uncovered)} uncovered"
        elif n_masts < int(n_cranes):
            status += f"  ·  {int(n_cranes) - n_masts} mast slot(s) unused"
        else:
            status += "  ·  all lifts OK"
        status_text.set_text(status)
        ax.set_title(title_base + f"\n{status}", fontsize=13, fontweight="bold")
        fig.canvas.draw_idle()

    def on_slider(val):
        render(int(val))

    slider.on_changed(on_slider)
    render(int(slider.val))

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {output_path}")

    print("Interactive mode — drag the Cranes slider (close window to exit).")
    plt.show()


def plot_heatmap(
    grid,
    x_centers,
    y_centers,
    df: pd.DataFrame,
    output_path: str,
    *,
    crane: dict | None = None,
    positions: list[dict] | None = None,
    footprint: np.ndarray | None = None,
    weights_t: pd.Series | None = None,
    capacity_rings: int = 8,
    iso_capacity: bool = False,
    iso_capacity_levels_t: list[float] | None = None,
):
    fig, ax = plt.subplots(figsize=(18, 12))
    ax.set_facecolor("#f0f0f0")

    vmax = np.percentile(grid[grid > 0], 98) if np.any(grid > 0) else 1.0
    display = np.ma.masked_where(grid <= vmax * 0.02, grid)
    cmap = plt.colormaps["OrRd"].copy()
    cmap.set_bad(color="#f0f0f0")
    mesh = ax.pcolormesh(
        x_centers,
        y_centers,
        display,
        cmap=cmap,
        shading="auto",
        alpha=0.95,
        vmin=0,
        vmax=vmax,
        zorder=1,
    )
    cbar = fig.colorbar(mesh, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Lift load intensity (kg/m², smoothed)", fontsize=10)

    outline_types = ["IfcWall", "IfcWallStandardCase", "IfcSlab"]
    for _, row in df[df["ifc_type"].isin(outline_types)].iterrows():
        if float(row.get("length_m", 0) or 0) < 0.05:
            continue
        if float(row["x_m"]) == 0.0 and float(row["y_m"]) == 0.0:
            continue
        corners = rect_corners(row)
        poly = mpatches.Polygon(
            corners,
            closed=True,
            fill=False,
            edgecolor="#666666",
            linewidth=0.4,
            alpha=0.5,
            zorder=2,
        )
        ax.add_patch(poly)

    # One footprint per column grid position (IFC exports stacked segments at same XY)
    columns = df[df["ifc_type"] == "IfcColumn"].copy()
    if not columns.empty:
        if (columns["length_m"] > 0.05).any():
            columns = columns[columns["length_m"] > 0.05]
            columns = columns.sort_values("length_m", ascending=False)
        columns = columns.assign(_gx=columns["x_m"].round(2), _gy=columns["y_m"].round(2))
        columns = columns.drop_duplicates(subset=["_gx", "_gy"])
        for _, row in columns.iterrows():
            corners = rect_corners(row)
            poly = mpatches.Polygon(
                corners,
                closed=True,
                facecolor=COLUMN_COLOR,
                edgecolor="white",
                linewidth=0.6,
                alpha=0.9,
                zorder=4,
            )
            ax.add_patch(poly)

    beams = df[df["ifc_type"] == "IfcBeam"].copy()
    if not beams.empty and (beams["length_m"] > 0.01).any():
        beams = beams[beams["length_m"] > 0.01]
        for _, row in beams.iterrows():
            corners = rect_corners(row)
            poly = mpatches.Polygon(
                corners,
                closed=True,
                facecolor="none",
                edgecolor=BEAM_COLOR,
                linewidth=1.2,
                alpha=0.95,
                zorder=4,
            )
            ax.add_patch(poly)

    for _, row in df[df["ifc_type"].isin(HIGHLIGHT_TYPES)].iterrows():
        if float(row["x_m"]) == 0.0 and float(row["y_m"]) == 0.0:
            continue
        ax.scatter(
            row["x_m"],
            row["y_m"],
            s=90,
            marker="s",
            color="#6a0dad",
            edgecolors="white",
            linewidths=0.8,
            zorder=5,
        )
        w = row["lift_weight_kg"] / 1000
        ax.annotate(
            f"{w:.0f}t",
            (row["x_m"], row["y_m"]),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=8,
            color="#4a0072",
            zorder=6,
        )

    if crane and positions:
        draw_crane_overlay(
            ax,
            positions,
            crane,
            footprint=footprint,
            show_footprint=True,
            annotate=True,
            weights=weights_t,
            df=df,
            capacity_rings=capacity_rings,
            iso_capacity=iso_capacity,
            iso_capacity_levels_t=iso_capacity_levels_t,
        )

    ax.set_xlabel("X (m)", fontsize=11)
    ax.set_ylabel("Y (m)", fontsize=11)
    ax.set_title(
        "Crane load heat map — 3-crane fleet near heaviest lifts (stairs, beams, columns)",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_aspect("equal")
    ax.grid(True, linestyle="--", linewidth=0.35, color="#bbbbbb", alpha=0.6, zorder=0)

    legend_handles = [
        mpatches.Patch(color="#fee0d2", label="Low lift load"),
        mpatches.Patch(color="#de2d26", label="High lift load"),
        mpatches.Patch(facecolor="none", edgecolor="#6a0dad", label="Stair (annotated tonnes)"),
        mpatches.Patch(facecolor="none", edgecolor=BEAM_COLOR, label="Beam"),
        mpatches.Patch(facecolor=COLUMN_COLOR, edgecolor="white", label="Column"),
    ]
    if crane and positions:
        from .geometric_visualizer import POSITION_COLORS

        legend_handles.append(
            mpatches.Patch(facecolor="none", edgecolor="#2c3e50", linestyle="-", label="Building footprint")
        )
        for i, pos in enumerate(positions):
            color = POSITION_COLORS[i % len(POSITION_COLORS)]
            rank = f"C{pos.get('crane_id', i + 1)}"
            r = pos.get("radius_m", crane["radius_m"])
            legend_handles.append(
                mpatches.Patch(
                    facecolor=color,
                    edgecolor=color,
                    alpha=0.35,
                    label=f"{rank} working r={r:.0f} m",
                )
            )
        if capacity_rings > 0:
            legend_handles.append(
                mpatches.Patch(
                    facecolor="none",
                    edgecolor="#555555",
                    linestyle="-",
                    alpha=0.6,
                    label="Iso-radius (outreach · max capacity)",
                )
            )
        if iso_capacity:
            legend_handles.append(
                mpatches.Patch(
                    facecolor="none",
                    edgecolor="#555555",
                    linestyle=":",
                    alpha=0.8,
                    label="Iso-capacity (max radius for load)",
                )
            )
    ax.legend(handles=legend_handles, loc="upper left", framealpha=0.92, fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {output_path}")


def main():
    args = parse_args()
    df = prepare_elements_df(pd.read_csv(args.csv))

    active = lift_extra_types(args.include_slabs, args.include_walls)
    lift_mask = lift_element_mask(df, extra_types=active)
    n_lb = int(df["load_bearing"].apply(parse_load_bearing).sum()) if "load_bearing" in df.columns else 0
    n_lift = int(lift_mask.sum())
    print(
        f"Lift elements: {n_lift} "
        f"(structural + load_bearing; {n_lb} via load_bearing=True)"
    )
    weights_by_gid = load_element_weights(args.weights_table)
    if weights_by_gid:
        print(f"Element weights from {args.weights_table} ({len(weights_by_gid)} items, mesh volume)")
    else:
        print(f"Warning: {args.weights_table} not found — run: python ifc_element_weights.py")

    grid, x_centers, y_centers, df = build_load_grid(
        df, args.resolution, args.smooth, active, weights_by_gid, args.beam_heat_width
    )

    crane = None
    positions = None
    footprint = None
    weights_t = None

    if not args.no_crane and args.top_positions > 0 and not args.interactive:
        config_path = Path(args.crane_config)
        if config_path.exists():
            weights_t = df["lift_weight_kg"] / 1000.0
            weights_t.name = "lift_weight_t"
            footprint = building_footprint(df)
            crane, positions, _, uncovered_df, jib_note = resolve_crane_and_fleet(
                config_path,
                footprint,
                df,
                weights_t,
                configuration=args.reeving,
                jib_length_m=args.jib_length,
                max_cranes=args.top_positions,
                extra_lift_types=active,
            )
            if jib_note:
                print(jib_note)
            if positions:
                print(f"\n{format_crane_config_block(crane)}")
                print(
                    f"\nFleet: {len(positions)} mast(s) of this same crane on the site plan "
                    f"(planner steps every {GRID_STEP:.0f} m outside the building)."
                )
                print("Rule: each lift needs capacity_t ≥ weight at its hook radius.")
                for pos in positions:
                    print(format_mast_line(pos, crane))
                if len(uncovered_df):
                    print(f"\n  Not liftable with {len(positions)} crane(s) ({len(uncovered_df)} elements):")
                    for _, el in uncovered_df.nlargest(5, "lift_weight_t").iterrows():
                        w = el["lift_weight_t"]
                        rmax = el.get("max_outreach_m")
                        hint = f"max hook radius {rmax:.0f} m" if pd.notna(rmax) else "exceeds chart (shorter jib?)"
                        print(
                            f"    {w:5.1f} t  {el['ifc_type']:12s}  "
                            f"({el['x_m']:.0f}, {el['y_m']:.0f})  {hint}"
                        )
            else:
                print("No valid crane positions found outside building footprint.")
        else:
            print(f"Crane config not found ({config_path}), skipping overlay.")

    iso_levels = None
    if args.iso_capacity_levels:
        iso_levels = [float(x.strip()) for x in args.iso_capacity_levels.split(",") if x.strip()]

    if args.interactive and not args.no_crane:
        config_path = Path(args.crane_config)
        if not config_path.exists():
            print(f"Crane config not found ({config_path}), cannot run interactive mode.")
            return
        weights_t = df["lift_weight_kg"] / 1000.0
        weights_t.name = "lift_weight_t"
        footprint = building_footprint(df)
        cfg = _read_crane_config(config_path)
        jib_note = None
        if args.jib_length is not None:
            crane = load_crane(config_path, configuration=args.reeving, jib_length_m=args.jib_length)
        else:
            crane, _, _, _, jib_note = select_optimal_jib(
                footprint, df, weights_t, cfg, args.reeving,
                max_cranes=args.max_cranes, extra_lift_types=active,
            )
            if jib_note:
                print(jib_note)
        n_lift = int((weights_t > 0).sum())
        print(f"Pre-computing fleet layouts for 1–{args.max_cranes} cranes…")
        fleet_cache = precache_fleets(
            crane, footprint, df, weights_t, args.max_cranes, active,
        )
        for n in range(1, args.max_cranes + 1):
            pos, unc, _ = fleet_cache[n]
            print(f"  {n} crane(s): {len(pos)} mast(s), {n_lift - len(unc)}/{n_lift} lifts covered")
        plot_heatmap_interactive(
            grid, x_centers, y_centers, df, crane, footprint, weights_t, fleet_cache,
            initial_cranes=args.top_positions,
            jib_note=jib_note,
            capacity_rings=args.capacity_rings,
            iso_capacity=args.iso_capacity,
            iso_capacity_levels_t=iso_levels,
            output_path=args.output,
        )
    else:
        plot_heatmap(
            grid,
            x_centers,
            y_centers,
            df,
            args.output,
            crane=crane,
            positions=positions,
            footprint=footprint,
            weights_t=weights_t,
            capacity_rings=args.capacity_rings,
            iso_capacity=args.iso_capacity,
            iso_capacity_levels_t=iso_levels,
        )

    top = df.nlargest(8, "lift_weight_kg")[["ifc_type", "name", "x_m", "y_m", "lift_weight_kg"]]
    print("\nHeaviest lift elements:")
    for _, row in top.iterrows():
        print(f"  {row['lift_weight_kg']/1000:6.1f} t  {row['ifc_type']:22s}  ({row['x_m']:.1f}, {row['y_m']:.1f})")


if __name__ == "__main__":
    main()
