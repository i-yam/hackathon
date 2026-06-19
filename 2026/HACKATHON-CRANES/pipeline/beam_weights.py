"""Backward-compatible re-exports — use element_weights.py instead."""

from .element_weights import (
    DEFAULT_BEAMS_TABLE,
    beam_weight_kg,
    load_beam_weights,
)

__all__ = ["DEFAULT_BEAMS_TABLE", "beam_weight_kg", "load_beam_weights"]
