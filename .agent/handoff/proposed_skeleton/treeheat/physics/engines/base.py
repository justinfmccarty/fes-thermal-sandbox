"""Canopy engine interface — the pluggable contract.

The canopy model is a CURRENT DROP-IN, not a permanent commitment (Li 2023 today;
a future team may swap it). Define this interface from the TWO engines that already
exist (li2023_ceb + legacy_leaf) so it is grounded, not speculative.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CanopyState:
    """Inputs a canopy engine needs for one solve (air temp, radiation, species, etc.).
    TODO: finalise fields from the CEB model's actual signature."""


@dataclass
class CanopyResult:
    """Engine output: leaf temperature + flux breakdown. TODO: finalise fields."""


class CanopyEngine(ABC):
    """All canopy models implement this. Selected by name in config."""

    name: str = "base"

    @abstractmethod
    def solve(self, state: "CanopyState") -> "CanopyResult":
        """Solve steady-state leaf temperature and fluxes for one tree-hour."""
        raise NotImplementedError
