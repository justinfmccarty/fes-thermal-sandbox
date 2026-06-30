"""Physics + canopy engine differential and integration tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ARCHIVE = REPO_ROOT / "src_archive"
V1_CONFIG = REPO_ROOT / "treeheat" / "config" / "config.yaml"
V0_CONFIG = SRC_ARCHIVE / "config.yaml"

# Fixed hot-hour fixture (identical inputs for v0 and v1)
HOT_HOUR = dict(
    Ta=35.0,
    RH=0.3,
    U=2.0,
    P=101.3,
    E_dir=600.0,
    E_dif=150.0,
    SVF=0.6,
    albedo=0.2,
    emissivity=0.95,
    Tg_prev=40.0,
    theta=0.30,
)


def _qa_from_rh(Ta: float, RH: float, P: float) -> float:
    es = 0.6108 * __import__("math").exp(17.27 * Ta / (Ta + 237.3))
    ea = RH * es
    return 0.622 * ea / P


def _vpd_from_rh(Ta: float, RH: float) -> float:
    es = 0.6108 * __import__("math").exp(17.27 * Ta / (Ta + 237.3))
    return es * (1.0 - RH)


@pytest.fixture
def v1_cfg():
    from treeheat.config import get_config, reload_config

    reload_config(V1_CONFIG)
    return get_config(V1_CONFIG)


@pytest.fixture
def v0_archive_path():
    if not V0_CONFIG.exists():
        pytest.skip("src_archive/config.yaml not available")
    path = str(SRC_ARCHIVE)
    if path not in sys.path:
        sys.path.insert(0, path)
    return str(V0_CONFIG)


def _impervious_props(cfg: dict, ground_model) -> tuple[float, float, float]:
    props = ground_model.get_ground_properties(
        "impervious",
        albedo=HOT_HOUR["albedo"],
        emissivity=HOT_HOUR["emissivity"],
    )
    return (
        props["heat_capacity"],
        props["evap_factor"],
        HOT_HOUR["albedo"],
    )


def test_v1_ceb_matches_v0_chain(v1_cfg, v0_archive_path):
    """Full ground -> soil -> CEB chain matches v0 for identical inputs."""
    pytest.importorskip("scipy")

    from ground_temperature import GroundEnergyBalance as V0Ground
    from li2023_ceb_model import CEBInputs, Li2023CEBModel
    from soil_moisture import SoilMoistureBucket as V0Soil

    from treeheat.physics.ground import GroundEnergyBalance as V1Ground
    from treeheat.physics.integrator import solve_tree_hour
    from treeheat.physics.soil_moisture import SoilMoistureBucket as V1Soil
    from treeheat.physics.species_params import default_species_params

    h = HOT_HOUR
    K_down = h["E_dir"] + h["E_dif"]
    K_up_dir = h["albedo"] * h["E_dir"]
    K_up_dif = h["albedo"] * h["E_dif"]
    qa = _qa_from_rh(h["Ta"], h["RH"], h["P"])
    VPD = _vpd_from_rh(h["Ta"], h["RH"])

    # --- v0 chain ---
    g0 = V0Ground(v0_archive_path)
    s0 = V0Soil(v0_archive_path)
    ceb0 = Li2023CEBModel(v0_archive_path)
    props0 = g0.get_ground_properties("impervious", albedo=h["albedo"], emissivity=h["emissivity"])
    gs0 = g0.step(
        h["Tg_prev"],
        K_down,
        h["Ta"],
        h["RH"],
        h["albedo"],
        h["emissivity"],
        props0["heat_capacity"],
        props0["evap_factor"],
        dt=3600.0,
        theta=h["theta"],
        theta_fc=0.35,
    )
    ss0 = s0.get_state(h["theta"], r_sto_min=160.0)
    defaults = __import__("config_locator").get_config(v0_archive_path).model.species_defaults
    ceb_in = CEBInputs(
        Ta=h["Ta"],
        RH=h["RH"],
        U=h["U"],
        P=h["P"],
        E_dir=h["E_dir"],
        E_dif=h["E_dif"],
        SVF=h["SVF"],
        albedo_g=h["albedo"],
        epsilon_g=h["emissivity"],
        alpha_sf=1.0 - defaults.alpha_leaf,
        alpha_lf=defaults.epsilon_leaf,
        epsilon_lf=defaults.epsilon_leaf,
        r_sto=ss0.r_sto,
        leaf_size=defaults.leaf_char_size,
        Tg=gs0.Tg,
    )
    out0 = ceb0.solve_leaf_temperature(ceb_in)
    Rn0 = out0.Q_sw + out0.Q_lw_in - out0.Q_lw_out

    # --- v1 chain via integrator ---
    g1 = V1Ground(v1_cfg)
    props1 = g1.get_ground_properties("impervious", albedo=h["albedo"], emissivity=h["emissivity"])
    L_sky = g1.calculate_longwave_sky(h["Ta"], h["RH"])
    species = default_species_params(v1_cfg)
    result = solve_tree_hour(
        tree_id=1,
        hour=4000,
        Ta=h["Ta"],
        RH=h["RH"],
        U=h["U"],
        P=h["P"],
        qa=qa,
        VPD=VPD,
        L_sky=L_sky,
        E_dir=h["E_dir"],
        E_dif=h["E_dif"],
        K_up_dir=K_up_dir,
        K_up_dif=K_up_dif,
        SVF=h["SVF"],
        albedo=h["albedo"],
        emissivity=h["emissivity"],
        heat_capacity=props1["heat_capacity"],
        evap_factor=props1["evap_factor"],
        species=species,
        Tg_prev=h["Tg_prev"],
        theta_prev=h["theta"],
        cfg=v1_cfg,
        ground_model=g1,
        soil_model=V1Soil(v1_cfg),
        engine_name="li2023_ceb",
    )

    assert gs0.Tg == pytest.approx(result.Tg, rel=1e-9, abs=1e-9)
    assert out0.Tf == pytest.approx(result.T_leaf, rel=1e-9, abs=1e-6)
    assert out0.H == pytest.approx(result.H, rel=1e-9, abs=1e-6)
    assert out0.LE == pytest.approx(result.LE, rel=1e-9, abs=1e-6)
    assert out0.Q_sw == pytest.approx(result.Kabs, rel=1e-9, abs=1e-6)
    assert Rn0 == pytest.approx(result.Rn, rel=1e-9, abs=1e-6)


def test_engine_swap_one_line_config(v1_cfg):
    """Both engines run through integrator; swap is config-only."""
    pytest.importorskip("scipy")

    from treeheat.physics.ground import GroundEnergyBalance
    from treeheat.physics.integrator import solve_tree_hour
    from treeheat.physics.soil_moisture import SoilMoistureBucket
    from treeheat.physics.species_params import default_species_params

    h = HOT_HOUR
    g = GroundEnergyBalance(v1_cfg)
    props = g.get_ground_properties("impervious", albedo=h["albedo"], emissivity=h["emissivity"])
    L_sky = g.calculate_longwave_sky(h["Ta"], h["RH"])
    qa = _qa_from_rh(h["Ta"], h["RH"], h["P"])
    VPD = _vpd_from_rh(h["Ta"], h["RH"])
    species = default_species_params(v1_cfg)
    common = dict(
        tree_id=1,
        hour=4000,
        Ta=h["Ta"],
        RH=h["RH"],
        U=h["U"],
        P=h["P"],
        qa=qa,
        VPD=VPD,
        L_sky=L_sky,
        E_dir=h["E_dir"],
        E_dif=h["E_dif"],
        K_up_dir=h["albedo"] * h["E_dir"],
        K_up_dif=h["albedo"] * h["E_dif"],
        SVF=h["SVF"],
        albedo=h["albedo"],
        emissivity=h["emissivity"],
        heat_capacity=props["heat_capacity"],
        evap_factor=props["evap_factor"],
        species=species,
        Tg_prev=h["Tg_prev"],
        theta_prev=h["theta"],
        cfg=v1_cfg,
        ground_model=g,
        soil_model=SoilMoistureBucket(v1_cfg),
    )

    ceb = solve_tree_hour(**common, engine_name="li2023_ceb")
    legacy = solve_tree_hour(**common, engine_name="legacy_leaf")

    assert ceb.converged
    assert legacy.converged
    assert 0.0 < ceb.T_leaf < 80.0
    assert 0.0 < legacy.T_leaf < 80.0
    assert ceb.T_leaf != legacy.T_leaf  # engines differ — both ran


def test_integrator_does_not_import_concrete_engines():
    """Integrator must depend only on get_engine(), not concrete models."""
    integrator_path = REPO_ROOT / "treeheat" / "treeheat" / "physics" / "integrator.py"
    source = integrator_path.read_text(encoding="utf-8")
    assert "li2023_ceb" not in source
    assert "legacy_leaf" not in source
    assert "Li2023CEB" not in source
    assert "LegacyLeaf" not in source
    assert "get_engine" in source
