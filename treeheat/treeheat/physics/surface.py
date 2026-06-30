"""Surface temperature and Mean Radiant Temperature (MRT).

PORT FROM: src_archive/surface_energy_balance.py
"""

from __future__ import annotations

import numpy as np

from treeheat.config import get_config

__all__ = [
    "calculate_longwave_in",
    "calculate_mrt",
    "calculate_surface_temperature",
    "get_sigma",
]


def get_sigma(cfg: dict | None = None) -> float:
    if cfg is None:
        cfg = get_config()
    return float(cfg["physical_constants"]["sigma"])


def calculate_surface_temperature(
    K_down: float,
    K_up: float,
    albedo: float,
    emissivity: float,
    Ta: float,
    L_sky: float,
    U: float = 2.0,
    h_conv: float = 10.0,
    cfg: dict | None = None,
) -> float:
    sigma = get_sigma(cfg)
    Ta_K = Ta + 273.15
    K_net = (1.0 - albedo) * K_down - K_up
    Tsurf_K = Ta_K
    for _ in range(20):
        L_net = emissivity * (L_sky - sigma * Tsurf_K**4)
        f = (
            emissivity * sigma * Tsurf_K**4
            + h_conv * Tsurf_K
            - (K_net + emissivity * L_sky + h_conv * Ta_K)
        )
        df = 4.0 * emissivity * sigma * Tsurf_K**3 + h_conv
        if abs(df) < 1e-10:
            break
        Tsurf_K_new = max(250.0, min(350.0, Tsurf_K - f / df))
        if abs(Tsurf_K_new - Tsurf_K) < 0.01:
            Tsurf_K = Tsurf_K_new
            break
        Tsurf_K = Tsurf_K_new
    return Tsurf_K - 273.15


def calculate_mrt(
    Tsurf: float,
    SVF: float,
    Ta: float,
    L_sky: float,
    cfg: dict | None = None,
) -> float:
    sigma = get_sigma(cfg)
    Tsurf_K = Tsurf + 273.15
    L_ground = sigma * Tsurf_K**4
    L_effective = SVF * L_sky + (1.0 - SVF) * L_ground
    T_mrt_K = (L_effective / sigma) ** 0.25
    return T_mrt_K - 273.15


def calculate_longwave_in(
    SVF: float,
    L_sky: float,
    L_air: float | None = None,
    Tsurf: float | None = None,
    cfg: dict | None = None,
) -> float:
    sigma = get_sigma(cfg)
    if L_air is None:
        if Tsurf is None:
            L_air = L_sky
        else:
            Tsurf_K = Tsurf + 273.15
            L_air = sigma * Tsurf_K**4
    return SVF * L_sky + (1.0 - SVF) * L_air
