"""Canopy engine interface — the pluggable contract.

The canopy model is a CURRENT DROP-IN, not a permanent commitment (Li 2023 today;
a future team may swap it). Defined from the TWO engines that already exist
(li2023_ceb + legacy_leaf).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from treeheat.physics.species_params import SpeciesParams


@dataclass
class CanopyState:
    """Inputs a canopy engine needs for one solve (superset for CEB + legacy)."""

    # Meteorology
    Ta: float
    RH: float  # fraction 0-1
    U: float
    P: float
    qa: float
    VPD: float
    L_sky: float

    # Radiation at sensor [W/m2]
    E_dir: float
    E_dif: float
    K_up_dir: float
    K_up_dif: float

    # Geometry
    SVF: float

    # Ground / surface
    albedo_g: float
    epsilon_g: float
    Tg: float
    Tsurf: float

    # Soil / stomatal coupling
    r_sto: float
    theta: float

    # Species physiology
    species: SpeciesParams


@dataclass
class CanopyResult:
    """Engine output: leaf temperature + flux breakdown."""

    T_leaf: float
    H: float
    LE: float
    gc: float
    rs: float
    Kabs: float
    Rn: float
    converged: bool = True


class CanopyEngine(ABC):
    """All canopy models implement this. Selected by name in config."""

    name: str = "base"

    @abstractmethod
    def solve(self, state: CanopyState) -> CanopyResult:
        """Solve steady-state leaf temperature and fluxes for one tree-hour."""
        raise NotImplementedError
