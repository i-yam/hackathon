#!/usr/bin/env python3
"""Export all IFC beams with section sizes and estimated weight.

For all element types use: python ifc_element_weights.py
"""

from __future__ import annotations

import argparse
import csv
import re

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import numpy as np

from .ifc_mesh import density_from_material, get_material_name, mesh_volume_m3
from .paths import BEAMS_TABLE_CSV, DEFAULT_IFC

IFC_PATH = DEFAULT_IFC
OUTPUT_PATH = BEAMS_TABLE_CSV

FIELDNAMES = [
    "tag",
    "name",
    "reference",
    "material",
    "span_m",
    "section_depth_mm",
    "section_width_mm",
    "section_depth_m",
    "section_width_m",
    "bbox_length_m",
    "bbox_width_m",
    "bbox_height_m",
    "volume_m3",
    "density_kg_m3",
    "weight_kg",
    "weight_t",
    "x_m",
    "y_m",
    "z_m",
    "global_id",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export beam sizes and weights from IFC.")
    parser.add_argument("--ifc", default=IFC_PATH)
    parser.add_argument("--output", default=OUTPUT_PATH)
    return parser.parse_args()


def density_from_material_beam(material: str) -> float:
    return density_from_material(material, default=7850.0)


def get_reference(element) -> str:
    psets = ifcopenshell.util.element.get_psets(element)
    for pset_name in ("Pset_BeamCommon", "Pset_QuantityTakeOff"):
        ref = psets.get(pset_name, {}).get("Reference")
        if ref:
            return str(ref)
    name = element.Name or ""
    if ":" in name:
        parts = name.split(":")
        if len(parts) >= 2:
            return parts[1]
    return ""


def parse_section_mm(reference: str) -> tuple[float | None, float | None]:
    match = re.search(r"(\d{3,4})\s*x\s*(\d{2,4})", reference)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def row_from_beam(settings, element) -> dict:
    reference = get_reference(element)
    material = get_material_name(element)
    rho = density_from_material_beam(material)

    depth_mm, width_mm = parse_section_mm(reference)
    depth_m = depth_mm / 1000.0 if depth_mm else None
    width_m = width_mm / 1000.0 if width_mm else None

    bbox_length = bbox_width = bbox_height = 0.0
    x_m = y_m = z_m = 0.0
    volume_m3 = 0.0
    span_m = 0.0

    try:
        shape = ifcopenshell.geom.create_shape(settings, element)
        geom = shape.geometry
        verts = np.array(geom.verts, dtype=float).reshape(-1, 3)
        faces = np.array(geom.faces, dtype=int).reshape(-1, 3)
        mn, mx = verts.min(axis=0), verts.max(axis=0)
        center = (mn + mx) / 2

        bbox_length = float(mx[0] - mn[0])
        bbox_width = float(mx[1] - mn[1])
        bbox_height = float(mx[2] - mn[2])
        x_m, y_m, z_m = float(center[0]), float(center[1]), float(center[2])
        span_m = max(bbox_length, bbox_width)
        volume_m3 = mesh_volume_m3(verts, faces)
    except Exception:
        pass

    if volume_m3 <= 0 and depth_m and width_m and span_m > 0:
        volume_m3 = span_m * depth_m * width_m

    if depth_mm is None and bbox_height > 0:
        depth_mm = round(bbox_height * 1000, 0)
        depth_m = bbox_height
    if width_mm is None:
        cross = min(bbox_length, bbox_width)
        if cross > 0:
            width_mm = round(cross * 1000, 0)
            width_m = cross

    weight_kg = volume_m3 * rho

    return {
        "tag": element.Tag or "",
        "name": element.Name or "",
        "reference": reference,
        "material": material,
        "span_m": round(span_m, 3),
        "section_depth_mm": depth_mm if depth_mm is not None else "",
        "section_width_mm": width_mm if width_mm is not None else "",
        "section_depth_m": round(depth_m, 3) if depth_m else "",
        "section_width_m": round(width_m, 3) if width_m else "",
        "bbox_length_m": round(bbox_length, 3),
        "bbox_width_m": round(bbox_width, 3),
        "bbox_height_m": round(bbox_height, 3),
        "volume_m3": round(volume_m3, 3),
        "density_kg_m3": rho,
        "weight_kg": round(weight_kg, 1),
        "weight_t": round(weight_kg / 1000, 2),
        "x_m": round(x_m, 3),
        "y_m": round(y_m, 3),
        "z_m": round(z_m, 3),
        "global_id": element.GlobalId,
    }


def export(ifc_path: str, output_path: str) -> int:
    ifc = ifcopenshell.open(ifc_path)
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)

    rows = [row_from_beam(settings, beam) for beam in ifc.by_type("IfcBeam")]
    rows.sort(key=lambda r: (r["reference"], r["tag"]))

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    total_t = sum(r["weight_t"] for r in rows)
    print(f"Exported {len(rows)} beams to {output_path}")
    print(f"Total beam weight: {total_t:.2f} t")
    return len(rows)


def main() -> None:
    args = parse_args()
    export(args.ifc, args.output)


if __name__ == "__main__":
    main()
