"""Element lift weights from element_weights.csv (IFC mesh volume)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .paths import BEAMS_TABLE_CSV, ELEMENT_WEIGHTS_CSV

DEFAULT_WEIGHTS_TABLE = ELEMENT_WEIGHTS_CSV
DEFAULT_BEAMS_TABLE = BEAMS_TABLE_CSV  # legacy fallback

# Always treated as crane lifts (even if IFC load_bearing is unset/false)
DEFAULT_STRUCTURAL_LIFT_TYPES = frozenset({"IfcColumn", "IfcBeam", "IfcStair"})


def parse_load_bearing(value) -> bool:
    """Parse load_bearing from CSV (True/False, 1/0, yes/no)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def is_lift_element(
    row: pd.Series,
    *,
    extra_types: set[str] | frozenset[str] | None = None,
) -> bool:
    """
    True when the element counts as a crane lift:
    - load_bearing is True (any IFC type — walls, slabs, etc.), or
    - ifc_type is a default structural lift (column, beam, stair).
    """
    if "load_bearing" in row.index and parse_load_bearing(row["load_bearing"]):
        return True
    types = set(DEFAULT_STRUCTURAL_LIFT_TYPES)
    if extra_types:
        types |= set(extra_types)
    return row.get("ifc_type") in types


def lift_element_mask(
    df: pd.DataFrame,
    *,
    extra_types: set[str] | frozenset[str] | None = None,
) -> pd.Series:
    """Boolean mask of rows that participate in lift heat map / fleet planning."""
    return df.apply(lambda r: is_lift_element(r, extra_types=extra_types), axis=1)


def load_element_weights(path: str | Path = DEFAULT_WEIGHTS_TABLE) -> dict[str, float]:
    """Load weights in kg keyed by global_id. Missing file → empty dict."""
    table = Path(path)
    if not table.exists():
        return {}

    df = pd.read_csv(table)
    if "weight_kg" not in df.columns or "global_id" not in df.columns:
        return {}

    return {
        str(gid): float(w)
        for gid, w in zip(df["global_id"], df["weight_kg"])
        if pd.notna(gid) and pd.notna(w)
    }


def element_weight_kg(row: pd.Series, by_gid: dict[str, float]) -> float | None:
    gid = row.get("global_id")
    if pd.notna(gid) and str(gid) in by_gid:
        return by_gid[str(gid)]
    return None


def load_beam_weights(path: str | Path = DEFAULT_BEAMS_TABLE) -> tuple[dict[str, float], dict[str, float]]:
    """Legacy API — prefer element_weights.csv; falls back to beams_table.csv."""
    weights = load_element_weights(DEFAULT_WEIGHTS_TABLE)
    if weights:
        return weights, {}

    table = Path(path)
    if not table.exists():
        return {}, {}

    df = pd.read_csv(table)
    by_gid = {
        str(gid): float(w)
        for gid, w in zip(df["global_id"], df["weight_kg"])
        if pd.notna(gid) and pd.notna(w)
    }
    by_ref: dict[str, float] = {}
    if "reference" in df.columns:
        for ref, group in df.groupby("reference"):
            if pd.notna(ref):
                by_ref[str(ref)] = float(group["weight_kg"].iloc[0])
    return by_gid, by_ref


def beam_weight_kg(row: pd.Series, by_gid: dict[str, float], by_ref: dict[str, float]) -> float | None:
    """Legacy beam lookup — uses global_id from element_weights or beams_table."""
    w = element_weight_kg(row, by_gid)
    if w is not None:
        return w
    ref = row.get("reference")
    if pd.notna(ref) and str(ref) in by_ref:
        return by_ref[str(ref)]
    return None
