#!/usr/bin/env python3
"""Export IFC elements to CSV with center position and oriented dimensions."""

from __future__ import annotations

import argparse
import csv

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import numpy as np

from .ifc_mesh import COLUMN_SECTION_M
from .paths import DEFAULT_IFC, IFC_ELEMENTS_CSV

IFC_PATH = DEFAULT_IFC
CSV_PATH = IFC_ELEMENTS_CSV

ELEMENT_TYPES = [
    "IfcWall",
    "IfcWallStandardCase",
    "IfcSlab",
    "IfcColumn",
    "IfcBeam",
    "IfcStair",
    "IfcBuildingElementProxy",
]

FIELDNAMES = [
    "global_id",
    "ifc_type",
    "name",
    "x_m",
    "y_m",
    "z_m",
    "x_min_m",
    "y_min_m",
    "z_min_m",
    "x_max_m",
    "y_max_m",
    "z_max_m",
    "length_m",
    "width_m",
    "height_m",
    "material",
    "thickness_m",
    "load_bearing",
    "is_external",
    "reference",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export IFC elements with dimensions to CSV.")
    parser.add_argument("--ifc", default=IFC_PATH)
    parser.add_argument("--output", default=CSV_PATH)
    return parser.parse_args()


def get_material_name(element) -> str:
    try:
        material = ifcopenshell.util.element.get_material(element)
    except Exception:
        return ""
    if material is None:
        return ""
    if hasattr(material, "Name") and material.Name:
        return material.Name
    return material.is_a()


def get_pset_value(element, pset_names: tuple[str, ...], key: str):
    psets = ifcopenshell.util.element.get_psets(element)
    for pset_name in pset_names:
        pset = psets.get(pset_name, {})
        if key in pset and pset[key] not in (None, ""):
            return pset[key]
    return ""


def axis_aligned_dims(verts: np.ndarray) -> dict[str, float]:
    """Axis-aligned bounding box in world coordinates (no rotation)."""
    mn = verts.min(axis=0)
    mx = verts.max(axis=0)
    return {
        "x_min_m": float(mn[0]),
        "y_min_m": float(mn[1]),
        "z_min_m": float(mn[2]),
        "x_max_m": float(mx[0]),
        "y_max_m": float(mx[1]),
        "z_max_m": float(mx[2]),
        "x_m": float((mn[0] + mx[0]) / 2),
        "y_m": float((mn[1] + mx[1]) / 2),
        "z_m": float((mn[2] + mx[2]) / 2),
        "length_m": float(mx[0] - mn[0]),
        "width_m": float(mx[1] - mn[1]),
        "height_m": float(mx[2] - mn[2]),
    }


def get_vertices(settings, element) -> np.ndarray | None:
    try:
        shape = ifcopenshell.geom.create_shape(settings, element)
    except Exception:
        return None
    verts = np.array(shape.geometry.verts, dtype=float).reshape(-1, 3)
    if len(verts) == 0:
        return None
    return verts


def row_from_element(settings, element) -> dict:
    verts = get_vertices(settings, element)
    if verts is not None:
        dims = axis_aligned_dims(verts)
    else:
        dims = {k: 0.0 for k in (
            "x_m", "y_m", "z_m", "x_min_m", "y_min_m", "z_min_m",
            "x_max_m", "y_max_m", "z_max_m", "length_m", "width_m", "height_m",
        )}

    length_m = dims["length_m"]
    width_m = dims["width_m"]
    height_m = dims["height_m"]

    if element.is_a() == "IfcColumn" and height_m > 0:
        half = COLUMN_SECTION_M / 2
        cx, cy = dims["x_m"], dims["y_m"]
        length_m = COLUMN_SECTION_M
        width_m = COLUMN_SECTION_M
        dims["length_m"] = length_m
        dims["width_m"] = width_m
        dims["x_min_m"] = cx - half
        dims["x_max_m"] = cx + half
        dims["y_min_m"] = cy - half
        dims["y_max_m"] = cy + half

    thickness = get_pset_value(
        element,
        ("Pset_WallCommon", "Pset_SlabCommon", "Pset_ColumnCommon", "Pset_BeamCommon"),
        "Thickness",
    )
    if thickness == "" and height_m > 0 and element.is_a() in ("IfcWall", "IfcWallStandardCase"):
        thickness = min(length_m, width_m) if min(length_m, width_m) > 0 else ""

    load_bearing = get_pset_value(
        element,
        ("Pset_WallCommon", "Pset_SlabCommon", "Pset_ColumnCommon", "Pset_BeamCommon"),
        "LoadBearing",
    )
    is_external = get_pset_value(
        element,
        ("Pset_WallCommon", "Pset_SlabCommon"),
        "IsExternal",
    )
    reference = get_pset_value(
        element,
        (
            "Pset_WallCommon",
            "Pset_SlabCommon",
            "Pset_ColumnCommon",
            "Pset_BeamCommon",
            "Pset_QuantityTakeOff",
            "Pset_StairCommon",
        ),
        "Reference",
    )

    name = element.Name or ""
    if not reference and ":" in name:
        reference = name.split(":")[1] if len(name.split(":")) > 1 else ""

    return {
        "global_id": element.GlobalId,
        "ifc_type": element.is_a(),
        "name": name,
        "x_m": round(dims["x_m"], 3),
        "y_m": round(dims["y_m"], 3),
        "z_m": round(dims["z_m"], 3),
        "x_min_m": round(dims["x_min_m"], 3),
        "y_min_m": round(dims["y_min_m"], 3),
        "z_min_m": round(dims["z_min_m"], 3),
        "x_max_m": round(dims["x_max_m"], 3),
        "y_max_m": round(dims["y_max_m"], 3),
        "z_max_m": round(dims["z_max_m"], 3),
        "length_m": round(length_m, 3),
        "width_m": round(width_m, 3),
        "height_m": round(height_m, 3),
        "material": get_material_name(element),
        "thickness_m": thickness if thickness == "" else round(float(thickness), 3),
        "load_bearing": load_bearing,
        "is_external": is_external,
        "reference": reference,
    }


def export(ifc_path: str, output_path: str) -> int:
    ifc = ifcopenshell.open(ifc_path)
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)

    rows: list[dict] = []
    skipped = 0
    for ifc_type in ELEMENT_TYPES:
        for element in ifc.by_type(ifc_type):
            row = row_from_element(settings, element)
            if row["length_m"] == 0 and row["width_m"] == 0:
                skipped += 1
            rows.append(row)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} elements to {output_path} ({skipped} without XY size)")
    return len(rows)


def main():
    args = parse_args()
    export(args.ifc, args.output)


if __name__ == "__main__":
    main()
