"""Legacy leaf energy balance — PRIOR engine, kept for comparison/validation.

PORT FROM: src_archive/leaf_energy_balance.py
Radiation pre-computation (Kabs, L_in, Rn) lives inside this engine.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import brentq

from treeheat.config import get_config
from treeheat.physics import surface
from treeheat.physics.engines.base import CanopyEngine, CanopyResult, CanopyState
from treeheat.physics.engines import register

__all__ = ["LegacyLeaf"]


@register
class LegacyLeaf(CanopyEngine):
    name = "legacy_leaf"

    def __init__(self, cfg: dict[str, Any] | None = None):
        if cfg is None:
            cfg = get_config()
        self._cfg = cfg
        pc = cfg["physical_constants"]
        self._rho_air = float(pc["rho_air"])
        self._cp_air = float(pc["cp_air"])
        self._lambda_v = float(pc["lambda_v"])
        self._sigma = float(pc["sigma"])

    @staticmethod
    def calculate_aerodynamic_resistance(
        U: float,
        ra_scale: float,
        shelter_factor: float,
        U_min: float = 0.5,
    ) -> float:
        U_eff = max(U * shelter_factor, U_min)
        return ra_scale / U_eff

    @staticmethod
    def calculate_qsat(T: float, P: float) -> float:
        esat = 0.6108 * np.exp(17.27 * T / (T + 237.3))
        return 0.622 * esat / P

    @staticmethod
    def calculate_vpd_from_q(T: float, q: float, P: float) -> float:
        esat = 0.6108 * np.exp(17.27 * T / (T + 237.3))
        ea = q * P / 0.622
        return max(0.0, esat - ea)

    def calculate_stomatal_conductance(
        self,
        species,
        Kabs: float,
        VPD: float,
        theta: float,
        T_leaf: float,
    ) -> float:
        f_rad = species.fRad(Kabs)
        f_vpd = species.fVPD(VPD)
        f_sm = species.fSM(theta)
        f_t = species.fT(T_leaf)
        gc = species.gc_max * f_rad * f_vpd * f_sm * f_t
        return max(0.0, gc)

    def calculate_net_radiation(
        self,
        Kabs: float,
        L_in: float,
        epsilon_leaf: float,
        T_leaf: float,
    ) -> float:
        T_leaf_K = T_leaf + 273.15
        return Kabs + epsilon_leaf * L_in - epsilon_leaf * self._sigma * T_leaf_K**4

    def energy_balance_residual(
        self,
        T_leaf: float,
        Rn: float,
        Ta_K: float,
        qa: float,
        ra: float,
        species,
        theta: float,
        P: float,
    ) -> float:
        T_leaf_K = T_leaf + 273.15
        H = self._rho_air * self._cp_air * (T_leaf_K - Ta_K) / ra
        Kabs = Rn
        VPD = self.calculate_vpd_from_q(T_leaf, qa, P)
        gc = self.calculate_stomatal_conductance(species, Kabs, VPD, theta, T_leaf)
        rs = 1.0 / gc if gc > 0 else 1e6
        qsat_leaf = self.calculate_qsat(T_leaf, P)
        LE = self._rho_air * self._lambda_v * (qsat_leaf - qa) / (ra + rs)
        return Rn - H - LE

    def solve(self, state: CanopyState) -> CanopyResult:
        sp = state.species
        K_down_total = state.E_dir + state.E_dif
        K_up_total = state.K_up_dir + state.K_up_dif
        Kabs = (
            sp.beta_above * (1.0 - sp.alpha_leaf) * K_down_total
            + sp.beta_below * (1.0 - sp.alpha_leaf) * K_up_total
        )
        L_in = surface.calculate_longwave_in(
            state.SVF, state.L_sky, Tsurf=state.Tsurf, cfg=self._cfg
        )
        Rn_initial = self.calculate_net_radiation(Kabs, L_in, sp.epsilon_leaf, state.Ta)

        Ta_K = state.Ta + 273.15
        ra = self.calculate_aerodynamic_resistance(
            state.U, sp.ra_scale, sp.shelter_factor
        )
        T_min = state.Ta - 10.0
        T_max = state.Ta + 30.0
        converged = True
        try:
            T_leaf = brentq(
                self.energy_balance_residual,
                T_min,
                T_max,
                args=(Rn_initial, Ta_K, state.qa, ra, sp, state.theta, state.P),
                xtol=0.1,
                maxiter=50,
            )
        except ValueError:
            T_leaf = state.Ta
            converged = False

        T_leaf_K = T_leaf + 273.15
        H = self._rho_air * self._cp_air * (T_leaf_K - Ta_K) / ra
        Rn_final = self.calculate_net_radiation(Kabs, L_in, sp.epsilon_leaf, T_leaf)
        VPD = self.calculate_vpd_from_q(T_leaf, state.qa, state.P)
        gc = self.calculate_stomatal_conductance(sp, Kabs, VPD, state.theta, T_leaf)
        rs = 1.0 / gc if gc > 0 else 1e6
        qsat_leaf = self.calculate_qsat(T_leaf, state.P)
        LE = self._rho_air * self._lambda_v * (qsat_leaf - state.qa) / (ra + rs)
        LE = max(0.0, Rn_final - H)

        return CanopyResult(
            T_leaf=T_leaf,
            H=H,
            LE=LE,
            gc=gc,
            rs=rs,
            Kabs=Kabs,
            Rn=Rn_final,
            converged=converged,
        )
