"""Root-zone soil moisture bucket; stomatal coupling.

PORT FROM: src_archive/soil_moisture.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from treeheat.config import get_config

__all__ = ["SoilMoistureBucket", "SoilMoistureState"]

RHO_WATER = 1000.0


@dataclass
class SoilMoistureState:
    """Container for soil moisture state and derived variables."""

    theta: float
    REW: float
    f_SM: float
    r_sto: float
    drainage: float
    ET: float


class SoilMoistureBucket:
    """Root-zone soil moisture bucket with stomatal stress coupling."""

    def __init__(self, cfg: dict[str, Any] | None = None):
        if cfg is None:
            cfg = get_config()
        soil = cfg["model"]["soil"]
        self._theta_fc = float(soil["theta_fc"])
        self._theta_wilt = float(soil["theta_wilt"])
        self._theta_sat = float(soil["theta_sat"])
        self._theta_init = float(soil["theta_init"])
        self._Z_r = float(soil["Z_r"])
        self._k_drain_default = float(soil["k_drain_default"])
        self._REW_crit = float(soil["REW_crit"])
        self._r_sto_min = float(soil["r_sto_min"])
        self._lambda_v = float(cfg["physical_constants"]["lambda_v"])

    def initialize(self, theta: float | None = None) -> float:
        return theta if theta is not None else self._theta_init

    def calculate_REW(self, theta: float) -> float:
        if self._theta_fc <= self._theta_wilt:
            return 0.0
        REW = (theta - self._theta_wilt) / (self._theta_fc - self._theta_wilt)
        return max(0.0, min(1.0, REW))

    def calculate_stress_factor(self, theta: float) -> float:
        REW = self.calculate_REW(theta)
        if REW >= self._REW_crit:
            return 1.0
        if REW <= 0:
            return 0.01
        return max(0.01, REW / self._REW_crit)

    def calculate_stomatal_resistance(
        self,
        theta: float,
        r_sto_min: float | None = None,
    ) -> float:
        r_min = r_sto_min if r_sto_min is not None else self._r_sto_min
        f_SM = self.calculate_stress_factor(theta)
        r_sto = r_min / f_SM
        return min(10000.0, r_sto)

    def calculate_drainage(
        self,
        theta: float,
        k_drain: float | None = None,
    ) -> float:
        k = k_drain if k_drain is not None else self._k_drain_default
        if theta > self._theta_fc:
            k_hourly = k / 24.0
            excess = theta - self._theta_fc
            return k_hourly * excess * self._Z_r
        return 0.0

    def et_from_le(self, LE: float) -> float:
        ET_ms = LE / (RHO_WATER * self._lambda_v)
        return ET_ms * 3600.0

    def step(
        self,
        theta_prev: float,
        LE: float,
        precip_mm: float = 0.0,
        dt: float = 3600.0,
        k_drain: float | None = None,
        r_sto_min: float | None = None,
    ) -> SoilMoistureState:
        P = precip_mm / 1000.0
        ET_mh = self.et_from_le(LE)
        ET = ET_mh * (dt / 3600.0)
        D_mh = self.calculate_drainage(theta_prev, k_drain)
        D = D_mh * (dt / 3600.0)
        dtheta = (P - ET - D) / self._Z_r
        theta_new = max(self._theta_wilt * 0.5, min(self._theta_sat, theta_prev + dtheta))
        REW = self.calculate_REW(theta_new)
        f_SM = self.calculate_stress_factor(theta_new)
        r_sto = self.calculate_stomatal_resistance(theta_new, r_sto_min)
        return SoilMoistureState(
            theta=theta_new,
            REW=REW,
            f_SM=f_SM,
            r_sto=r_sto,
            drainage=D_mh,
            ET=ET_mh,
        )

    def get_state(
        self,
        theta: float,
        r_sto_min: float | None = None,
    ) -> SoilMoistureState:
        REW = self.calculate_REW(theta)
        f_SM = self.calculate_stress_factor(theta)
        r_sto = self.calculate_stomatal_resistance(theta, r_sto_min)
        drainage = self.calculate_drainage(theta)
        return SoilMoistureState(
            theta=theta,
            REW=REW,
            f_SM=f_SM,
            r_sto=r_sto,
            drainage=drainage,
            ET=0.0,
        )

    @property
    def theta_fc(self) -> float:
        return self._theta_fc

    @property
    def theta_init(self) -> float:
        return self._theta_init
