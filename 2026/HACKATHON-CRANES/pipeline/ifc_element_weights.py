#!/usr/bin/env python3
"""Export IFC element lift weights from mesh volume (not bounding boxes)."""

from __future__ import annotations

import argparse
import csv

import ifcopenshell
import ifcopenshell.geom

from .ifc_mesh import column_volume_m3, density_from_material, get_material_name, shape_metrics
from .paths import DEFAULT_IFC, ELEMENT_WEIGHTS_CSV

IFC_PATH = DEFAULT_IFC
OUTPUT_PATH = ELEMENT_WEIGHTS_CSV

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
    "tag",
    "name",
    "material",
    "volume_m3",
    "bbox_volume_m3",
    "density_kg_m3",
    "weight_kg",
    "weight_t",
    "x_m",
    "y_m",
    "z_m",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export mesh-based element weights from IFC.")
    parser.add_argument("--ifc", default=IFC_PATH)
    parser.add_argument("--output", default=OUTPUT_PATH)
    parser.add_argument(
        "--types",
        nargs="*",
        default=ELEMENT_TYPES,
        help="IFC types to export (default: all structural types)",
    )
    return parser.parse_args()


def row_from_element(settings, element) -> dict | None:
    metrics = shape_metrics(settings, element)
    if metrics is None or metrics["volume_m3"] <= 0:
        return None

    material = get_material_name(element)
    ifc_type = element.is_a()
    default_rho = 7850.0 if ifc_type == "IfcBeam" else 2400.0
    rho = density_from_material(material, default=default_rho)

    volume_m3 = metrics["volume_m3"]
    if ifc_type == "IfcColumn":
        volume_m3 = column_volume_m3(metrics["bbox_height_m"])

    weight_kg = volume_m3 * rho

    return {
        "global_id": element.GlobalId,
        "ifc_type": ifc_type,
        "tag": element.Tag or "",
        "name": element.Name or "",
        "material": material,
        "volume_m3": round(volume_m3, 4),
        "bbox_volume_m3": round(metrics["bbox_volume_m3"], 4),
        "density_kg_m3": rho,
        "weight_kg": round(weight_kg, 1),
        "weight_t": round(weight_kg / 1000, 3),
        "x_m": round(metrics["x_m"], 3),
        "y_m": round(metrics["y_m"], 3),
        "z_m": round(metrics["z_m"], 3),
    }


def export(ifc_path: str, output_path: str, element_types: list[str]) -> int:
    ifc = ifcopenshell.open(ifc_path)
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)

    rows: list[dict] = []
    skipped = 0
    for ifc_type in element_types:
        for element in ifc.by_type(ifc_type):
            row = row_from_element(settings, element)
            if row is None:
                skipped += 1
                continue
            rows.append(row)

    rows.sort(key=lambda r: (r["ifc_type"], r["name"], r["tag"]))

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    total_t = sum(r["weight_t"] for r in rows)
    print(f"Exported {len(rows)} elements to {output_path} ({skipped} without mesh)")
    print(f"Total weight: {total_t:.2f} t")
    for t in element_types:
        sub = [r for r in rows if r["ifc_type"] == t]
        if sub:
            print(f"  {t}: {len(sub)} items, {sum(r['weight_t'] for r in sub):.2f} t")
    return len(rows)


def main() -> None:
    args = parse_args()
    export(args.ifc, args.output, args.types)


if __name__ == "__main__":
    main()
