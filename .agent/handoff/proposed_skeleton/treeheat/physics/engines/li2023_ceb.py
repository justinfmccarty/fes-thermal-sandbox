"""Li et al. (2023) canopy energy balance — CURRENT DEFAULT engine.

PORT FROM: src_archive/li2023_ceb_model.py
Reference: Li, Zhang & Wang (2023), Sustainable Cities and Society 99:104994.
Register as "li2023_ceb"; set as default in config/defaults.yaml.
"""
from __future__ import annotations
from .base import CanopyEngine, CanopyState, CanopyResult
from . import register


@register
class Li2023CEB(CanopyEngine):
    name = "li2023_ceb"

    def solve(self, state: CanopyState) -> CanopyResult:
        raise NotImplementedError("Port from src_archive/li2023_ceb_model.py")
