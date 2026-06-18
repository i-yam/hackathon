"""Laedt die normative Wissensbasis (DIN 4109) aus data/*.json.

Trennt Daten (JSON, gut zitier- und pruefbar) von Logik (engine.py).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parents[2] / "data"


@lru_cache(maxsize=1)
def materials() -> dict:
    return json.loads((_DATA / "materials.json").read_text(encoding="utf-8"))["materialien"]


@lru_cache(maxsize=1)
def requirements() -> dict:
    return json.loads((_DATA / "requirements.json").read_text(encoding="utf-8"))["rollen"]


@lru_cache(maxsize=1)
def _alias_index() -> dict:
    idx: dict[str, str] = {}
    for key, m in materials().items():
        idx[key.lower()] = key
        for alias in m.get("aliases", []):
            idx[alias.lower()] = key
    return idx


def resolve_material(name: str) -> tuple[str, dict] | tuple[None, None]:
    """Findet einen Materialeintrag ueber Name oder Alias (case-insensitiv, robust)."""
    if not name:
        return None, None
    idx = _alias_index()
    key = idx.get(name.strip().lower())
    if key is None:
        # weicher Match: Teilstring
        n = name.strip().lower()
        for alias, k in idx.items():
            if alias in n or n in alias:
                key = k
                break
    if key is None:
        return None, None
    return key, materials()[key]


def requirement_for(din_rolle: str) -> dict | None:
    return requirements().get(din_rolle)
