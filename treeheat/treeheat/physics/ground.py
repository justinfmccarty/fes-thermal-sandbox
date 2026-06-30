"""Ground temperature Tg (1-layer surface energy balance).

PORT FROM: src_archive/ground_temperature.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from treeheat.config import get_config

__all__ = [
    "GroundEnergyBalance",
    "GroundState",
    "get_ground_type_from_material",
]


@dataclass
class GroundState:
    """Container for ground temperature state."""

    Tg: float
    R_net: float
    H_g: float
    LE_g: float
    G: float


class GroundEnergyBalance:
    """1-layer ground surface energy balance model."""

    def __init__(self, cfg: dict[str, Any] | None = None):
        if cfg is None:
            cfg = get_config()
        self._cfg = cfg
        pc = cfg["physical_constants"]
        self._sigma = float(pc["sigma"])
        self._rho_air = float(pc["rho_air"])
        self._cp_air = float(pc["cp_air"])
        self._lambda_v = float(pc["lambda_v"])

        ground = cfg["model"]["ground"]
        self._r_a_ground = float(ground["r_a_ground"])
        self._ET_pot_ref = float(ground["ET_pot_ref"])

        self._ground_types: dict[str, dict[str, float]] = {}
        for type_name in ("impervious", "pervious", "vegetated"):
            type_config = ground["types"][type_name]
            self._ground_types[type_name] = {
                "heat_capacity": float(type_config["heat_capacity"]),
                "evap_factor": float(type_config["evap_factor"]),
                "k_drain": float(type_config["k_drain"]),
            }

    def get_ground_properties(
        self,
        ground_type: str,
        albedo: float | None = None,
        emissivity: float | None = None,
        heat_capacity: float | None = None,
        evap_factor: float | None = None,
    ) -> dict[str, float]:
        if ground_type not in self._ground_types:
            ground_type = "impervious"
        props = dict(self._ground_types[ground_type])
        if albedo is not None:
            props["albedo"] = albedo
        if emissivity is not None:
            props["emissivity"] = emissivity
        if heat_capacity is not None:
            props["heat_capacity"] = heat_capacity
        if evap_factor is not None:
            props["evap_factor"] = evap_factor
        return props

    def calculate_longwave_sky(self, Ta: float, RH: float = 0.5) -> float:
        Ta_K = Ta + 273.15
        e_sat = 0.6108 * np.exp(17.27 * Ta / (Ta + 237.3))
        e_a = RH * e_sat
        w = 46.5 * e_a / Ta_K
        epsilon_atm = 1.0 - (1.0 + w) * np.exp(-np.sqrt(1.2 + 3.0 * w))
        return epsilon_atm * self._sigma * Ta_K**4

    def calculate_sensible_heat(self, Tg: float, Ta: float) -> float:
        return self._rho_air * self._cp_air * (Tg - Ta) / self._r_a_ground

    def calculate_latent_heat(
        self,
        Tg: float,
        Ta: float,
        RH: float,
        evap_factor: float,
        theta: float | None = None,
        theta_fc: float | None = None,
    ) -> float:
        if evap_factor <= 0:
            return 0.0
        e_sat_g = 0.6108 * np.exp(17.27 * Tg / (Tg + 237.3))
        e_sat_a = 0.6108 * np.exp(17.27 * Ta / (Ta + 237.3))
        e_a = RH * e_sat_a
        VPD = max(0.0, e_sat_g - e_a)
        ET_pot = self._ET_pot_ref / 86400.0 * 1000.0
        vpd_scale = min(2.0, VPD / 1.0)
        moisture_factor = 1.0
        if theta is not None and theta_fc is not None and theta_fc > 0:
            moisture_factor = min(1.0, theta / theta_fc)
        return evap_factor * moisture_factor * vpd_scale * ET_pot * self._lambda_v / 1000.0

    def step(
        self,
        Tg_prev: float,
        K_down: float,
        Ta: float,
        RH: float,
        albedo: float,
        emissivity: float,
        heat_capacity: float,
        evap_factor: float,
        dt: float = 3600.0,
        theta: float | None = None,
        theta_fc: float | None = None,
    ) -> GroundState:
        Tg_K = Tg_prev + 273.15
        K_abs = (1.0 - albedo) * K_down
        L_sky = self.calculate_longwave_sky(Ta, RH)
        L_up = emissivity * self._sigma * Tg_K**4
        R_net = K_abs + L_sky - L_up
        H_g = self.calculate_sensible_heat(Tg_prev, Ta)
        LE_g = self.calculate_latent_heat(Tg_prev, Ta, RH, evap_factor, theta, theta_fc)
        G = R_net - H_g - LE_g
        dTg = G * dt / heat_capacity
        Tg_new = max(-40.0, min(80.0, Tg_prev + dTg))
        return GroundState(Tg=Tg_new, R_net=R_net, H_g=H_g, LE_g=LE_g, G=G)

    def equilibrium_temperature(
        self,
        K_down: float,
        Ta: float,
        RH: float,
        albedo: float,
        emissivity: float,
        evap_factor: float,
        theta: float | None = None,
        theta_fc: float | None = None,
        max_iter: int = 50,
        tol: float = 0.1,
    ) -> float:
        Tg = Ta + 5.0
        L_sky = self.calculate_longwave_sky(Ta, RH)
        K_abs = (1.0 - albedo) * K_down
        for _ in range(max_iter):
            Tg_K = Tg + 273.15
            L_up = emissivity * self._sigma * Tg_K**4
            R_net = K_abs + L_sky - L_up
            H_g = self.calculate_sensible_heat(Tg, Ta)
            LE_g = self.calculate_latent_heat(Tg, Ta, RH, evap_factor, theta, theta_fc)
            imbalance = R_net - H_g - LE_g
            dR_dT = -4.0 * emissivity * self._sigma * Tg_K**3
            dH_dT = self._rho_air * self._cp_air / self._r_a_ground
            dTg = imbalance / (dH_dT - dR_dT)
            Tg_new = Tg + dTg
            if abs(dTg) < tol:
                return Tg_new
            Tg = Tg_new
        return Tg


def get_ground_type_from_material(
    material_name: str,
    material_db_row: dict | None = None,
) -> str:
    if material_db_row is not None and "ground_type" in material_db_row:
        gt = material_db_row.get("ground_type", "")
        if gt in ("impervious", "pervious", "vegetated"):
            return str(gt)
    name_lower = material_name.lower()
    if any(v in name_lower for v in ("grass", "vegetation", "soil", "turf", "living")):
        return "vegetated"
    if any(p in name_lower for p in ("paver", "aggregate", "gravel", "permeable", "limestone")):
        return "pervious"
    return "impervious"
