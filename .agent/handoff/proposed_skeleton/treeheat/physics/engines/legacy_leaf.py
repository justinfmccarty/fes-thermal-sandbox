"""Legacy leaf energy balance — PRIOR engine, kept for comparison/validation.

PORT FROM: src_archive/leaf_energy_balance.py
Not deprecated — useful as a cross-check and to stress-test the engine interface.
If its signature won't fit CanopyEngine cleanly, design the interface around CEB
and adapt this one to it.
"""
from __future__ import annotations
from .base import CanopyEngine, CanopyState, CanopyResult
from . import register


@register
class LegacyLeaf(CanopyEngine):
    name = "legacy_leaf"

    def solve(self, state: CanopyState) -> CanopyResult:
        raise NotImplementedError("Port from src_archive/leaf_energy_balance.py")
