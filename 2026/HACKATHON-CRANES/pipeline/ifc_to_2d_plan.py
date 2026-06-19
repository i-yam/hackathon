#!/usr/bin/env python3
"""Generate a 2D floor plan from an IFC file using IfcOpenShell."""

from __future__ import annotations

import argparse
from collections import defaultdict

import ifcopenshell
import ifcopenshell.geom
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.collections import LineCollection, PolyCollection
from scipy.spatial import ConvexHull

from .paths import DEFAULT_IFC, PLAN_2D_PNG

IFC_PATH = DEFAULT_IFC
OUTPUT_PATH = PLAN_2D_PNG

ELEMENT_TYPES = [
    "IfcWall",
    "IfcWallStandardCase",
    "IfcSlab",
    "IfcColumn",
    "IfcBeam",
    "IfcStair",
    "IfcBuildingElementProxy",
]

STYLE = {
    "IfcWall": {"color": "#4a4a4a", "alpha": 0.9, "lw": 1.2, "label": "Wall"},
    "IfcWallStandardCase": {"color": "#4a4a4a", "alpha": 0.9, "lw": 1.2, "label": "Wall"},
    "IfcSlab": {"color": "#b8c5d6", "alpha": 0.35, "lw": 0.6, "label": "Slab", "fill": True},
    "IfcColumn": {"color": "#c00000", "alpha": 0.95, "lw": 1.0, "label": "Column", "fill": True},
    "IfcBeam": {"color": "#ed7d31", "alpha": 0.9, "lw": 1.5, "label": "Beam"},
    "IfcStair": {"color": "#7030a0", "alpha": 0.8, "lw": 1.0, "label": "Stair", "fill": True},
    "IfcBuildingElementProxy": {"color": "#0070c0", "alpha": 0.85, "lw": 1.0, "label": "Equipment"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a 2D plan from an IFC model.")
    parser.add_argument("--ifc", default=IFC_PATH, help="Path to IFC file")
    parser.add_argument("--output", default=OUTPUT_PATH, help="Output image path")
    parser.add_argument(
        "--z-min",
        type=float,
        default=None,
        help="Only include geometry with Z max above this value (m)",
    )
    parser.add_argument(
        "--z-max",
        type=float,
        default=None,
        help="Only include geometry with Z min below this value (m)",
    )
    parser.add_argument(
        "--mode",
        choices=["footprint", "slice"],
        default="footprint",
        help="footprint = project all geometry to XY; slice = keep verts inside Z band",
    )
    return parser.parse_args()


def get_vertices(settings, element) -> np.ndarray | None:
    try:
        shape = ifcopenshell.geom.create_shape(settings, element)
    except Exception:
        return None
    verts = np.array(shape.geometry.verts, dtype=float).reshape(-1, 3)
    if len(verts) == 0:
        return None
    return verts


def filter_by_z(verts: np.ndarray, z_min: float | None, z_max: float | None, mode: str) -> np.ndarray | None:
    if z_min is None and z_max is None:
        return verts

    if mode == "slice":
        mask = np.ones(len(verts), dtype=bool)
        if z_min is not None:
            mask &= verts[:, 2] >= z_min
        if z_max is not None:
            mask &= verts[:, 2] <= z_max
        filtered = verts[mask]
        if len(filtered) < 2:
            return None
        return filtered

    z_low, z_high = verts[:, 2].min(), verts[:, 2].max()
    if z_min is not None and z_high < z_min:
        return None
    if z_max is not None and z_low > z_max:
        return None
    return verts


def xy_hull(verts: np.ndarray) -> np.ndarray | None:
    xy = verts[:, :2]
    if len(xy) < 3:
        if len(xy) == 1:
            return xy
        return xy

    unique = np.unique(np.round(xy, 4), axis=0)
    if len(unique) < 3:
        return unique

    try:
        hull = ConvexHull(unique)
        return unique[hull.vertices]
    except Exception:
        x0, x1 = unique[:, 0].min(), unique[:, 0].max()
        y0, y1 = unique[:, 1].min(), unique[:, 1].max()
        return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])


def beam_segment(verts: np.ndarray) -> np.ndarray | None:
    xy = verts[:, :2]
    if len(xy) < 2:
        return None
    # Long axis of bounding box approximates beam centerline in plan
    dx = xy[:, 0].max() - xy[:, 0].min()
    dy = xy[:, 1].max() - xy[:, 1].min()
    if dx >= dy:
        y = xy[:, 1].mean()
        return np.array([[xy[:, 0].min(), y], [xy[:, 0].max(), y]])
    x = xy[:, 0].mean()
    return np.array([[x, xy[:, 1].min()], [x, xy[:, 1].max()]])


def collect_geometry(ifc_path: str, z_min: float | None, z_max: float | None, mode: str):
    ifc = ifcopenshell.open(ifc_path)
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)

    polygons: dict[str, list[np.ndarray]] = defaultdict(list)
    lines: dict[str, list[np.ndarray]] = defaultdict(list)
    skipped = 0

    for ifc_type in ELEMENT_TYPES:
        for element in ifc.by_type(ifc_type):
            verts = get_vertices(settings, element)
            if verts is None:
                skipped += 1
                continue
            verts = filter_by_z(verts, z_min, z_max, mode)
            if verts is None:
                continue

            if ifc_type == "IfcBeam":
                seg = beam_segment(verts)
                if seg is not None:
                    lines[ifc_type].append(seg)
                continue

            hull = xy_hull(verts)
            if hull is None or len(hull) == 0:
                skipped += 1
                continue
            polygons[ifc_type].append(hull)

    return polygons, lines, skipped


def plot_plan(polygons, lines, output_path: str, title: str):
    fig, ax = plt.subplots(figsize=(20, 14))
    ax.set_facecolor("#fafafa")

    draw_order = ["IfcSlab", "IfcWall", "IfcWallStandardCase", "IfcStair", "IfcColumn", "IfcBeam", "IfcBuildingElementProxy"]

    for ifc_type in draw_order:
        style = STYLE[ifc_type]
        polys = polygons.get(ifc_type, [])
        if polys and style.get("fill"):
            collection = PolyCollection(
                polys,
                facecolors=style["color"],
                edgecolors=style["color"],
                linewidths=style["lw"],
                alpha=style["alpha"],
                zorder=2 if ifc_type == "IfcSlab" else 3,
            )
            ax.add_collection(collection)
        elif polys:
            collection = PolyCollection(
                polys,
                facecolors="none",
                edgecolors=style["color"],
                linewidths=style["lw"],
                alpha=style["alpha"],
                zorder=3,
            )
            ax.add_collection(collection)

        segs = lines.get(ifc_type, [])
        if segs:
            collection = LineCollection(
                segs,
                colors=style["color"],
                linewidths=style["lw"] * 1.5,
                alpha=style["alpha"],
                zorder=4,
            )
            ax.add_collection(collection)

    all_pts = []
    for polys in polygons.values():
        for poly in polys:
            all_pts.append(poly)
    for segs in lines.values():
        for seg in segs:
            all_pts.append(seg)

    if not all_pts:
        raise SystemExit("No geometry found for the selected Z range.")

    stacked = np.vstack(all_pts)
    pad = 5
    ax.set_xlim(stacked[:, 0].min() - pad, stacked[:, 0].max() + pad)
    ax.set_ylim(stacked[:, 1].min() - pad, stacked[:, 1].max() + pad)
    ax.set_aspect("equal")
    ax.grid(True, linestyle="--", linewidth=0.4, color="#cccccc")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title(title, fontsize=14, fontweight="bold")

    handles = []
    seen = set()
    for ifc_type in draw_order:
        label = STYLE[ifc_type]["label"]
        if label in seen:
            continue
        if polygons.get(ifc_type) or lines.get(ifc_type):
            handles.append(mpatches.Patch(color=STYLE[ifc_type]["color"], label=label))
            seen.add(label)

    ax.legend(handles=handles, loc="upper right", framealpha=0.9)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180, bbox_inches="tight")
    print(f"Saved: {output_path}")


def main():
    args = parse_args()
    polygons, lines, skipped = collect_geometry(args.ifc, args.z_min, args.z_max, args.mode)

    total = sum(len(v) for v in polygons.values()) + sum(len(v) for v in lines.values())
    print(f"Plotted {total} elements ({skipped} skipped)")

    z_part = ""
    if args.z_min is not None or args.z_max is not None:
        lo = args.z_min if args.z_min is not None else "-inf"
        hi = args.z_max if args.z_max is not None else "+inf"
        z_part = f" | Z: {lo} to {hi} m"
    title = f"2D Plan - {args.ifc}{z_part}"
    plot_plan(polygons, lines, args.output, title)


if __name__ == "__main__":
    main()
