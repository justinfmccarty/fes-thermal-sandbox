"""Li et al. (2023) canopy energy balance — CURRENT DEFAULT engine.

PORT FROM: src_archive/li2023_ceb_model.py
Reference: Li, Zhang & Wang (2023), Sustainable Cities and Society 99:104994.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import brentq

from treeheat.config import get_config
from treeheat.physics.engines.base import CanopyEngine, CanopyResult, CanopyState
from treeheat.physics.engines import register

__all__ = ["Li2023CEB"]


@register
class Li2023CEB(CanopyEngine):
    name = "li2023_ceb"

    def __init__(self, cfg: dict[str, Any] | None = None):
        if cfg is None:
            cfg = get_config()
        self._cfg = cfg
        pc = cfg["physical_constants"]
        self._sigma = float(pc["sigma"])
        self._rho_air = float(pc["rho_air"])
        self._cp_air = float(pc["cp_air"])
        self._lambda_v = float(pc["lambda_v"])
        self._ceb = cfg["model"]["ceb"]

    def calculate_shortwave_at_leaf(
        self,
        E_dir: float,
        E_dif: float,
        albedo_g: float,
    ) -> tuple[float, float]:
        beta_dir = float(self._ceb["beta_dir"])
        beta_dif = float(self._ceb["beta_dif"])
        R_sw_dir = beta_dir * E_dir + albedo_g * E_dir * beta_dir
        R_sw_dif = beta_dif * E_dif
        return R_sw_dir, R_sw_dif

    def calculate_absorbed_shortwave(
        self,
        R_sw_dir: float,
        R_sw_dif: float,
        alpha_sf: float,
    ) -> float:
        return alpha_sf * (R_sw_dir + R_sw_dif)

    def calculate_sky_longwave(self, Ta_K: float) -> float:
        return -170.9 + 1.195 * self._sigma * Ta_K**4

    def calculate_longwave_components(
        self,
        Ta: float,
        SVF: float,
        epsilon_g: float,
        Tg: float | None = None,
    ) -> tuple[float, float, float, float]:
        Ta_K = Ta + 273.15
        delta_Tw = float(self._ceb["delta_Tw"])
        epsilon_w = float(self._ceb["epsilon_w"])
        if Tg is not None:
            Tg_used = Tg
            Tg_K = Tg + 273.15
        else:
            delta_Tg = float(self._ceb["delta_Tg"])
            Tg_used = Ta + delta_Tg
            Tg_K = Ta_K + delta_Tg
        Tw_K = Ta_K + delta_Tw
        R_lw_sky = self.calculate_sky_longwave(Ta_K)
        R_lw_down = SVF * R_lw_sky
        R_lw_up = epsilon_g * self._sigma * Tg_K**4
        R_lw_env = (1.0 - SVF) * epsilon_w * self._sigma * Tw_K**4
        return R_lw_down, R_lw_up, R_lw_env, Tg_used

    def calculate_absorbed_longwave(
        self,
        R_lw_down: float,
        R_lw_up: float,
        R_lw_env: float,
        alpha_lf: float,
    ) -> float:
        return alpha_lf * (R_lw_down + R_lw_up + R_lw_env)

    def calculate_emitted_longwave(self, Tf_K: float, epsilon_lf: float) -> float:
        return 2.0 * epsilon_lf * self._sigma * Tf_K**4

    def calculate_boundary_resistances(
        self,
        U: float,
        leaf_size: float,
    ) -> tuple[float, float]:
        A = float(self._ceb["A_coeff"])
        U_eff = max(U, 0.1)
        rb_h = A * (leaf_size / U_eff) ** 0.5
        rb_w = rb_h / 1.08
        return rb_h, rb_w

    @staticmethod
    def calculate_saturation_vapor_pressure(T: float) -> float:
        return 0.6108 * np.exp(17.27 * T / (T + 237.3))

    def calculate_vapor_pressure_slope(self, T: float) -> float:
        es = self.calculate_saturation_vapor_pressure(T)
        return 4098.0 * es / (T + 237.3) ** 2

    def calculate_vpd(self, Ta: float, RH: float) -> float:
        es_Ta = self.calculate_saturation_vapor_pressure(Ta)
        return es_Ta * (1.0 - RH)

    def calculate_sensible_heat(self, Tf: float, Ta: float, rb_h: float) -> float:
        return self._rho_air * self._cp_air * (Tf - Ta) / rb_h

    def calculate_latent_heat(
        self,
        Tf: float,
        Ta: float,
        D: float,
        s: float,
        P: float,
        rb_w: float,
        r_sto: float,
    ) -> float:
        vpd_leaf = max(0.0, D + s * (Tf - Ta))
        return 0.622 * self._lambda_v * self._rho_air * vpd_leaf / (P * (rb_w + r_sto))

    def energy_balance_residual(
        self,
        Tf: float,
        alpha_sf: float,
        alpha_lf: float,
        epsilon_lf: float,
        Ta: float,
        P: float,
        r_sto: float,
        R_sw_dir: float,
        R_sw_dif: float,
        R_lw_down: float,
        R_lw_up: float,
        R_lw_env: float,
        rb_h: float,
        rb_w: float,
        D: float,
        s: float,
    ) -> float:
        Tf_K = Tf + 273.15
        Q_sw = self.calculate_absorbed_shortwave(R_sw_dir, R_sw_dif, alpha_sf)
        Q_lw_in = self.calculate_absorbed_longwave(R_lw_down, R_lw_up, R_lw_env, alpha_lf)
        Q_lw_out = self.calculate_emitted_longwave(Tf_K, epsilon_lf)
        H = self.calculate_sensible_heat(Tf, Ta, rb_h)
        LE = self.calculate_latent_heat(Tf, Ta, D, s, P, rb_w, r_sto)
        return Q_sw + Q_lw_in - Q_lw_out - H - LE

    def solve(self, state: CanopyState) -> CanopyResult:
        sp = state.species
        RH = state.RH / 100.0 if state.RH > 1.0 else state.RH
        alpha_sf = 1.0 - sp.alpha_leaf
        alpha_lf = sp.epsilon_leaf
        epsilon_lf = sp.epsilon_leaf

        R_sw_dir, R_sw_dif = self.calculate_shortwave_at_leaf(
            state.E_dir, state.E_dif, state.albedo_g
        )
        R_lw_down, R_lw_up, R_lw_env, _Tg_used = self.calculate_longwave_components(
            state.Ta, state.SVF, state.epsilon_g, state.Tg
        )
        rb_h, rb_w = self.calculate_boundary_resistances(state.U, sp.leaf_char_size)
        D = self.calculate_vpd(state.Ta, RH)
        s = self.calculate_vapor_pressure_slope(state.Ta)

        T_min = state.Ta + float(self._ceb["T_min_offset"])
        T_max = state.Ta + float(self._ceb["T_max_offset"])
        converged = True
        try:
            Tf = brentq(
                self.energy_balance_residual,
                T_min,
                T_max,
                args=(
                    alpha_sf,
                    alpha_lf,
                    epsilon_lf,
                    state.Ta,
                    state.P,
                    state.r_sto,
                    R_sw_dir,
                    R_sw_dif,
                    R_lw_down,
                    R_lw_up,
                    R_lw_env,
                    rb_h,
                    rb_w,
                    D,
                    s,
                ),
                xtol=float(self._ceb["solver_xtol"]),
                maxiter=int(self._ceb["solver_maxiter"]),
            )
        except ValueError:
            Tf = state.Ta
            converged = False

        Tf_K = Tf + 273.15
        Q_sw = self.calculate_absorbed_shortwave(R_sw_dir, R_sw_dif, alpha_sf)
        Q_lw_in = self.calculate_absorbed_longwave(R_lw_down, R_lw_up, R_lw_env, alpha_lf)
        Q_lw_out = self.calculate_emitted_longwave(Tf_K, epsilon_lf)
        H = self.calculate_sensible_heat(Tf, state.Ta, rb_h)
        LE = self.calculate_latent_heat(Tf, state.Ta, D, s, state.P, rb_w, state.r_sto)
        Rn = Q_sw + Q_lw_in - Q_lw_out

        T_K = state.Ta + 273.15
        Vm = 8.314 * T_K / (state.P * 1000.0)
        gc = 1.0 / (state.r_sto * Vm) if state.r_sto > 0 else 0.0

        return CanopyResult(
            T_leaf=Tf,
            H=H,
            LE=LE,
            gc=gc,
            rs=state.r_sto,
            Kabs=Q_sw,
            Rn=Rn,
            converged=converged,
        )
