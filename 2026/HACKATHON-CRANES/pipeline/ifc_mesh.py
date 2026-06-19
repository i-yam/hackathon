"""Shared IFC mesh volume and material helpers."""

from __future__ import annotations

import ifcopenshell.util.element
import numpy as np

# Rectangular columns in IFC use a wall-like profile; lift weight uses 0.4×0.4 m section.
COLUMN_SECTION_M = 0.4

MATERIAL_DENSITY = {
    "metall": 7850,
    "baustahl": 7850,
    "stahl": 7850,
    "beton": 2400,
    "betonfertigteil": 2400,
    "ortbeton": 2400,
    "doka": 7850,
}


def density_from_material(material: str, default: float = 2400.0) -> float:
    if not material:
        return default
    key = material.lower()
    for token, rho in MATERIAL_DENSITY.items():
        if token in key:
            return float(rho)
    return default


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


def column_volume_m3(height_m: float, section_m: float = COLUMN_SECTION_M) -> float:
    """Column volume from square cross-section and vertical mesh height."""
    if height_m <= 0:
        return 0.0
    return section_m * section_m * height_m


def mesh_volume_m3(verts: np.ndarray, faces: np.ndarray) -> float:
    vol = 0.0
    for f in faces:
        v0, v1, v2 = verts[f[0]], verts[f[1]], verts[f[2]]
        vol += np.dot(v0, np.cross(v1, v2)) / 6.0
    return abs(vol)


def shape_metrics(settings, element) -> dict | None:
    import ifcopenshell.geom

    try:
        shape = ifcopenshell.geom.create_shape(settings, element)
    except Exception:
        return None

    geom = shape.geometry
    verts = np.array(geom.verts, dtype=float).reshape(-1, 3)
    faces = np.array(geom.faces, dtype=int).reshape(-1, 3)
    if len(verts) == 0:
        return None

    mn, mx = verts.min(axis=0), verts.max(axis=0)
    center = (mn + mx) / 2
    bbox = mx - mn
    volume_m3 = mesh_volume_m3(verts, faces)

    return {
        "x_m": float(center[0]),
        "y_m": float(center[1]),
        "z_m": float(center[2]),
        "bbox_length_m": float(bbox[0]),
        "bbox_width_m": float(bbox[1]),
        "bbox_height_m": float(bbox[2]),
        "bbox_volume_m3": float(bbox[0] * bbox[1] * bbox[2]),
        "volume_m3": volume_m3,
    }
