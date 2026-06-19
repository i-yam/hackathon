#!/usr/bin/env python3
"""Plot 2D plan from ifc_elements.csv using axis-aligned rectangles."""

from __future__ import annotations

import argparse

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd

from .paths import IFC_ELEMENTS_CSV, SCHEME_2D_PNG

CSV_PATH = IFC_ELEMENTS_CSV
OUTPUT_PATH = SCHEME_2D_PNG

FLOOR_PRESETS = {
    "all": (None, None, "all floors"),
    "deep_basement": (-99, -6, "deep basement (z < -6 m)"),
    "basement": (-6, -2, "basement (-6 to -2 m)"),
    "ground": (-2, 2, "ground (-2 to 2 m)"),
    "level1": (2, 6, "level 1 (2 to 6 m)"),
    "level2": (6, 10, "level 2 (6 to 10 m)"),
    "level3": (10, 14, "level 3 (10 to 14 m)"),
}

type_styles = {
    "IfcColumn": {"color": "#c00000", "fill": True, "lw": 0.8, "label": "Column"},
    "IfcBeam": {"color": "#ed7d31", "fill": False, "lw": 1.5, "label": "Beam"},
    "IfcWall": {"color": "#4a4a4a", "fill": False, "lw": 1.0, "label": "Wall"},
    "IfcWallStandardCase": {"color": "#4a4a4a", "fill": False, "lw": 1.0, "label": "Wall"},
    "IfcSlab": {"color": "#b8c5d6", "fill": True, "lw": 0.5, "label": "Slab"},
    "IfcStair": {"color": "#7030a0", "fill": True, "lw": 0.8, "label": "Stair"},
    "IfcBuildingElementProxy": {"color": "#0070c0", "fill": True, "lw": 0.8, "label": "Equipment"},
}

draw_order = [
    "IfcSlab",
    "IfcWall",
    "IfcWallStandardCase",
    "IfcStair",
    "IfcColumn",
    "IfcBeam",
    "IfcBuildingElementProxy",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot 2D scheme from ifc_elements.csv.")
    parser.add_argument("--csv", default=CSV_PATH)
    parser.add_argument("--output", default=OUTPUT_PATH)
    parser.add_argument(
        "--floor",
        choices=list(FLOOR_PRESETS),
        default="basement",
        help="Which floor band to show (default: basement, the busiest level in this model)",
    )
    parser.add_argument("--z-min", type=float, default=None, help="Override floor preset lower Z (m)")
    parser.add_argument("--z-max", type=float, default=None, help="Override floor preset upper Z (m)")
    return parser.parse_args()


def resolve_z_range(args: argparse.Namespace) -> tuple[float | None, float | None, str]:
    preset_min, preset_max, label = FLOOR_PRESETS[args.floor]
    z_min = args.z_min if args.z_min is not None else preset_min
    z_max = args.z_max if args.z_max is not None else preset_max
    if args.z_min is not None or args.z_max is not None:
        lo = z_min if z_min is not None else "-inf"
        hi = z_max if z_max is not None else "+inf"
        label = f"custom Z band ({lo} to {hi} m)"
    return z_min, z_max, label


def filter_by_z(df: pd.DataFrame, z_min: float | None, z_max: float | None) -> pd.DataFrame:
    if z_min is None and z_max is None:
        return df

    if {"z_min_m", "z_max_m"}.issubset(df.columns):
        mask = pd.Series(True, index=df.index)
        if z_min is not None:
            mask &= df["z_max_m"] >= z_min
        if z_max is not None:
            mask &= df["z_min_m"] <= z_max
        return df[mask].copy()

    mask = pd.Series(True, index=df.index)
    if z_min is not None:
        mask &= df["z_m"] >= z_min
    if z_max is not None:
        mask &= df["z_m"] <= z_max
    return df[mask].copy()


def load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    for col in ("length_m", "width_m", "x_min_m", "y_min_m", "z_min_m", "z_max_m"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["has_shape"] = (df["length_m"] > 0.01) & (df["width_m"] > 0.01)

    if "x_min_m" not in df.columns:
        df["x_min_m"] = df["x_m"] - df["length_m"] / 2
        df["y_min_m"] = df["y_m"] - df["width_m"] / 2

    return df[df["has_shape"]].copy()


def plot(df: pd.DataFrame, output_path: str, floor_label: str) -> None:
    if df.empty:
        raise SystemExit("No elements in the selected Z range.")

    fig, ax = plt.subplots(figsize=(18, 12))
    ax.set_facecolor("#f8f8f8")

    df = df.copy()
    df["_order"] = df["ifc_type"].apply(lambda t: draw_order.index(t) if t in draw_order else 99)
    df = df.sort_values("_order")

    for _, row in df.iterrows():
        ifc = row["ifc_type"]
        style = type_styles.get(ifc, {"color": "#888888", "fill": False, "lw": 1.0, "label": ifc})
        rect = mpatches.Rectangle(
            (row["x_min_m"], row["y_min_m"]),
            row["length_m"],
            row["width_m"],
            facecolor=style["color"] if style["fill"] else "none",
            edgecolor=style["color"],
            linewidth=style["lw"],
            alpha=0.75 if style["fill"] else 0.95,
            zorder=2 if ifc == "IfcSlab" else 3,
        )
        ax.add_patch(rect)

    pad = 5
    if "x_max_m" in df.columns:
        x0, x1 = df["x_min_m"].min(), df["x_max_m"].max()
        y0, y1 = df["y_min_m"].min(), df["y_max_m"].max()
    else:
        x0 = df["x_min_m"].min()
        x1 = (df["x_min_m"] + df["length_m"]).max()
        y0 = df["y_min_m"].min()
        y1 = (df["y_min_m"] + df["width_m"]).max()
    ax.set_xlim(x0 - pad, x1 + pad)
    ax.set_ylim(y0 - pad, y1 + pad)

    ax.set_aspect("equal")
    ax.grid(True, linestyle="--", linewidth=0.4, color="#cccccc", zorder=0)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title(f"2D Plan - {floor_label}", fontsize=14, fontweight="bold")

    handles = []
    seen = set()
    for ifc_type in draw_order:
        label = type_styles[ifc_type]["label"]
        if label in seen or ifc_type not in df["ifc_type"].values:
            continue
        style = type_styles[ifc_type]
        handles.append(
            mpatches.Patch(
                facecolor=style["color"] if style["fill"] else "none",
                edgecolor=style["color"],
                linewidth=1.2,
                label=label,
            )
        )
        seen.add(label)

    ax.legend(handles=handles, title="Element type", loc="upper right", framealpha=0.9)
    ax.xaxis.set_major_locator(plt.MultipleLocator(10))
    ax.yaxis.set_major_locator(plt.MultipleLocator(5))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {output_path} ({len(df)} elements, {floor_label})")


def main():
    args = parse_args()
    z_min, z_max, floor_label = resolve_z_range(args)
    df = load_data(args.csv)
    df = filter_by_z(df, z_min, z_max)
    plot(df, args.output, floor_label)


if __name__ == "__main__":
    main()
