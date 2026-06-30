"""Biophysical integrator — couples ground, surface, soil, and the canopy ENGINE.

PORT FROM: src_archive/biophysical_tree_stress.py (BiophysicalTreeStressCalculator).

Contract:
  - Per tree, per hour: assemble state, call the selected canopy engine, return
    leaf temperature + fluxes + surface/MRT.
  - MUST NOT import a concrete canopy model. It depends only on engines.base.CanopyEngine,
    obtained via engines.get_engine(config['model']['canopy_engine']).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from treeheat.config import get_config
from treeheat.physics.engines.base import CanopyState
from treeheat.physics.engines import get_engine
from treeheat.physics.ground import GroundEnergyBalance
from treeheat.physics import surface
from treeheat.physics.soil_moisture import SoilMoistureBucket
from treeheat.physics.species_params import SpeciesParams

__all__ = ["HourlyTreeResult", "run_biophysics", "solve_tree_hour"]


@dataclass
class HourlyTreeResult:
    """One tree-hour simulation record."""

    tree_id: int | str
    hour: int
    T_leaf: float
    Tg: float
    Tsurf: float
    MRT: float
    ET: float
    LE: float
    H: float
    gc: float
    rs: float
    theta: float
    REW: float
    f_SM: float
    VPD: float
    Kabs: float
    Rn: float
    converged: bool


def solve_tree_hour(
    *,
    tree_id: int | str,
    hour: int,
    Ta: float,
    RH: float,
    U: float,
    P: float,
    qa: float,
    VPD: float,
    L_sky: float,
    E_dir: float,
    E_dif: float,
    K_up_dir: float,
    K_up_dif: float,
    SVF: float,
    albedo: float,
    emissivity: float,
    heat_capacity: float,
    evap_factor: float,
    species: SpeciesParams,
    Tg_prev: float,
    theta_prev: float,
    precip_mm: float = 0.0,
    dt: float = 3600.0,
    cfg: dict[str, Any] | None = None,
    ground_model: GroundEnergyBalance | None = None,
    soil_model: SoilMoistureBucket | None = None,
    engine_name: str | None = None,
) -> HourlyTreeResult:
    """Run ground -> soil -> surface -> canopy engine -> soil update for one tree-hour."""
    if cfg is None:
        cfg = get_config()
    if ground_model is None:
        ground_model = GroundEnergyBalance(cfg)
    if soil_model is None:
        soil_model = SoilMoistureBucket(cfg)
    if engine_name is None:
        engine_name = cfg["model"]["canopy_engine"]

    RH_frac = RH / 100.0 if RH > 1.0 else RH
    K_down_total = E_dir + E_dif
    K_up_total = K_up_dir + K_up_dif
    theta_fc = soil_model.theta_fc

    ground_state = ground_model.step(
        Tg_prev=Tg_prev,
        K_down=K_down_total,
        Ta=Ta,
        RH=RH_frac,
        albedo=albedo,
        emissivity=emissivity,
        heat_capacity=heat_capacity,
        evap_factor=evap_factor,
        dt=dt,
        theta=theta_prev,
        theta_fc=theta_fc,
    )
    Tg = ground_state.Tg

    soil_state = soil_model.get_state(theta_prev, r_sto_min=species.r_sto)
    r_sto_dynamic = soil_state.r_sto
    REW = soil_state.REW
    f_SM = soil_state.f_SM

    Tsurf = surface.calculate_surface_temperature(
        K_down_total,
        K_up_total,
        albedo,
        emissivity,
        Ta,
        L_sky,
        U,
        cfg=cfg,
    )
    MRT = surface.calculate_mrt(Tsurf, SVF, Ta, L_sky, cfg=cfg)

    canopy_state = CanopyState(
        Ta=Ta,
        RH=RH_frac,
        U=U,
        P=P,
        qa=qa,
        VPD=VPD,
        L_sky=L_sky,
        E_dir=E_dir,
        E_dif=E_dif,
        K_up_dir=K_up_dir,
        K_up_dif=K_up_dif,
        SVF=SVF,
        albedo_g=albedo,
        epsilon_g=emissivity,
        Tg=Tg,
        Tsurf=Tsurf,
        r_sto=r_sto_dynamic,
        theta=theta_prev,
        species=species,
    )

    engine = get_engine(engine_name)
    canopy_result = engine.solve(canopy_state)

    new_soil = soil_model.step(
        theta_prev=theta_prev,
        LE=canopy_result.LE,
        precip_mm=precip_mm,
        dt=dt,
        r_sto_min=species.r_sto,
    )

    return HourlyTreeResult(
        tree_id=tree_id,
        hour=hour,
        T_leaf=canopy_result.T_leaf,
        Tg=Tg,
        Tsurf=Tsurf,
        MRT=MRT,
        ET=new_soil.ET,
        LE=canopy_result.LE,
        H=canopy_result.H,
        gc=canopy_result.gc,
        rs=canopy_result.rs,
        theta=new_soil.theta,
        REW=REW,
        f_SM=f_SM,
        VPD=VPD,
        Kabs=canopy_result.Kabs,
        Rn=canopy_result.Rn,
        converged=canopy_result.converged,
    )


def run_biophysics(
    tree_hours: list[dict[str, Any]],
    cfg: dict[str, Any] | None = None,
) -> list[HourlyTreeResult]:
    """Thin loop over solve_tree_hour for provided tree-hour input dicts."""
    if cfg is None:
        cfg = get_config()
    ground_model = GroundEnergyBalance(cfg)
    soil_model = SoilMoistureBucket(cfg)
    results: list[HourlyTreeResult] = []
    state: dict[Any, dict[str, float]] = {}

    for row in tree_hours:
        tid = row["tree_id"]
        if tid not in state:
            state[tid] = {
                "Tg": row.get("Tg_init", row["Ta"] + 5.0),
                "theta": row.get("theta_init", soil_model.theta_init),
            }
        result = solve_tree_hour(
            tree_id=tid,
            hour=row["hour"],
            Ta=row["Ta"],
            RH=row["RH"],
            U=row["U"],
            P=row["P"],
            qa=row["qa"],
            VPD=row["VPD"],
            L_sky=row["L_sky"],
            E_dir=row["E_dir"],
            E_dif=row["E_dif"],
            K_up_dir=row["K_up_dir"],
            K_up_dif=row["K_up_dif"],
            SVF=row["SVF"],
            albedo=row["albedo"],
            emissivity=row["emissivity"],
            heat_capacity=row["heat_capacity"],
            evap_factor=row["evap_factor"],
            species=row["species"],
            Tg_prev=state[tid]["Tg"],
            theta_prev=state[tid]["theta"],
            precip_mm=row.get("precip_mm", 0.0),
            dt=row.get("dt", 3600.0),
            cfg=cfg,
            ground_model=ground_model,
            soil_model=soil_model,
            engine_name=row.get("engine_name"),
        )
        state[tid]["Tg"] = result.Tg
        state[tid]["theta"] = result.theta
        results.append(result)
    return results
