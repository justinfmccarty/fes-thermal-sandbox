"""Engine-facing species parameters — CSV record + config defaults + Jarvis funcs.

PORT FROM: src_archive/tree_species.py (TreeSpecies class)

Maps io.species.SpeciesRecord fields to engine names and merges config defaults
for parameters not in the CSV (beta_above, r_sto, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from treeheat.config import get_config
from treeheat.io.species import SpeciesRecord

__all__ = ["SpeciesParams", "species_params_from_record", "default_species_params"]


@dataclass
class SpeciesParams:
    """Physiological parameters for canopy engines (legacy Jarvis + CEB)."""

    species_name: str
    alpha_leaf: float
    epsilon_leaf: float
    gc_max: float
    vpd_sensitivity: float
    T_opt: float
    T_crit: float
    beta_above: float
    beta_below: float
    ra_scale: float
    shelter_factor: float
    SVF: float
    r_sto: float
    leaf_char_size: float
    light_extinction_coefficient: float
    _theta_crit: float
    _theta_wilt: float

    def fRad(self, Kabs: float) -> float:
        """Radiation response for stomatal conductance."""
        K_sat = 800.0
        return min(1.0, max(0.0, Kabs / K_sat))

    def fVPD(self, VPD: float) -> float:
        """VPD response for stomatal conductance."""
        if VPD <= 0:
            return 1.0
        fvpd = np.exp(-VPD / self.vpd_sensitivity)
        return max(0.0, min(1.0, fvpd))

    def fSM(self, theta: float) -> float:
        """Soil moisture response — thresholds from soil.theta_fc / theta_wilt."""
        if theta >= self._theta_crit:
            return 1.0
        if theta <= self._theta_wilt:
            return 0.0
        return (theta - self._theta_wilt) / (self._theta_crit - self._theta_wilt)

    def fT(self, T_leaf: float) -> float:
        """Temperature response around T_opt."""
        T_min = self.T_opt - 15.0
        T_max = self.T_opt + 15.0
        if T_leaf < T_min or T_leaf > T_max:
            return 0.0
        if T_leaf == self.T_opt:
            return 1.0
        if T_leaf < self.T_opt:
            return (T_leaf - T_min) / (self.T_opt - T_min)
        return (T_max - T_leaf) / (T_max - self.T_opt)


def _species_defaults(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg["model"]["species_defaults"]


def _soil_thresholds(cfg: dict[str, Any]) -> tuple[float, float]:
    """fSM thresholds: v0 risk lacks theta_crit/theta_wilt — use soil field capacity."""
    soil = cfg["model"]["soil"]
    return float(soil["theta_fc"]), float(soil["theta_wilt"])


def species_params_from_record(
    record: SpeciesRecord,
    cfg: dict[str, Any] | None = None,
) -> SpeciesParams:
    """Build SpeciesParams from a validated CSV record + config defaults."""
    if cfg is None:
        cfg = get_config()
    defaults = _species_defaults(cfg)
    theta_crit, theta_wilt = _soil_thresholds(cfg)

    leaf_size = record.leaf_char_size
    if leaf_size is None:
        leaf_size = float(defaults["leaf_char_size"])

    return SpeciesParams(
        species_name=record.species,
        alpha_leaf=float(record.leaf_shortwave_albedo),
        epsilon_leaf=float(record.leaf_emissivity),
        gc_max=float(record.max_stomatal_conductance_mol_m2_s),
        vpd_sensitivity=float(record.vpd_sensitivity_g1_kpa_sqrt),
        T_opt=float(record.optimal_leaf_temperature_c),
        T_crit=float(record.critical_leaf_temperature_c),
        beta_above=float(defaults["beta_above"]),
        beta_below=float(defaults["beta_below"]),
        ra_scale=float(defaults["ra_scale"]),
        shelter_factor=float(defaults["shelter_factor"]),
        SVF=float(defaults["SVF"]),
        r_sto=float(defaults["r_sto"]),
        leaf_char_size=float(leaf_size),
        light_extinction_coefficient=float(record.light_extinction_coefficient),
        _theta_crit=theta_crit,
        _theta_wilt=theta_wilt,
    )


def default_species_params(cfg: dict[str, Any] | None = None) -> SpeciesParams:
    """Fallback species using config.model.species_defaults only."""
    if cfg is None:
        cfg = get_config()
    defaults = _species_defaults(cfg)
    theta_crit, theta_wilt = _soil_thresholds(cfg)
    return SpeciesParams(
        species_name="default",
        alpha_leaf=float(defaults["alpha_leaf"]),
        epsilon_leaf=float(defaults["epsilon_leaf"]),
        gc_max=float(defaults["gc_max"]),
        vpd_sensitivity=float(defaults["vpd_sensitivity"]),
        T_opt=float(defaults["T_opt"]),
        T_crit=float(defaults["T_crit"]),
        beta_above=float(defaults["beta_above"]),
        beta_below=float(defaults["beta_below"]),
        ra_scale=float(defaults["ra_scale"]),
        shelter_factor=float(defaults["shelter_factor"]),
        SVF=float(defaults["SVF"]),
        r_sto=float(defaults["r_sto"]),
        leaf_char_size=float(defaults["leaf_char_size"]),
        light_extinction_coefficient=float(defaults["light_extinction_coefficient"]),
        _theta_crit=theta_crit,
        _theta_wilt=theta_wilt,
    )
