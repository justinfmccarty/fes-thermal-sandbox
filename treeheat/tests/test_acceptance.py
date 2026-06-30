"""ACCEPTANCE GATE — the port is 'done' when it reproduces the paper's numbers.

Target (from src_archive/analysis_outputs/analysis_report.md, 25 scenarios, 147 trees):
  - Risk vs albedo:     slope ~ +61 %/unit,  R^2 ~ 0.87
  - Risk vs emissivity: slope ~ -194 %/unit, R^2 ~ 0.64
  - Best:  scenario_004 (~ -5% vs 50/50 ref)
  - Worst: scenario_020 (~ +13% vs 50/50 ref)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from treeheat.config import get_config, get_path, reload_config
from treeheat.risk.analysis import (
    REFERENCE_SCENARIO,
    load_v0_biophysical_results,
    run_analysis_pipeline,
)

# v0 paper headline targets (analysis_report.md)
V0_ALBEDO_SLOPE = 61.04
V0_ALBEDO_R2 = 0.871
V0_EMISSIVITY_SLOPE = -194.21
V0_BEST_SCENARIO = "scenario_004"
V0_WORST_SCENARIO = "scenario_020"
V0_BEST_PCT = -5.21
V0_WORST_PCT = 12.76


def _project_config() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "config.yaml"


@pytest.fixture(scope="module")
def project_cfg():
    config_path = _project_config()
    if not config_path.exists():
        pytest.skip("Project config not found")
    reload_config(config_path)
    return get_config(config_path)


@pytest.fixture(scope="module")
def v0_reference(project_cfg):
    ref_dir = get_path("v0_reference_dir", project_cfg)
    if not ref_dir.exists():
        pytest.skip("v0 reference dir not available")
    return ref_dir


def _load_v0_sensitivity(v0_reference: Path) -> pd.DataFrame:
    path = v0_reference / "sensitivity_analysis.csv"
    if not path.exists():
        pytest.skip("v0 sensitivity_analysis.csv not found")
    return pd.read_csv(path)


def _load_v0_pct_change(v0_reference: Path) -> pd.DataFrame:
    path = v0_reference / "pct_change_summary.csv"
    if not path.exists():
        pytest.skip("v0 pct_change_summary.csv not found")
    return pd.read_csv(path)


def _run_v1_analysis_from_v0_csvs(project_cfg) -> object:
    results = load_v0_biophysical_results(project_cfg)
    if len(results) < 25:
        pytest.skip("Frozen v0 biophysical CSVs not available")
    return run_analysis_pipeline(results, cfg=project_cfg, save_plots=False)


def test_fast_tier_reproduces_v0_sensitivity(project_cfg, v0_reference):
    """Fast tier: v1 analysis on frozen v0 biophysical CSVs matches v0 numbers."""
    analysis = _run_v1_analysis_from_v0_csvs(project_cfg)
    v0_sens = _load_v0_sensitivity(v0_reference)
    v0_pct = _load_v0_pct_change(v0_reference)

    reg = analysis.regression
    assert "risk_albedo" in reg
    assert "risk_emissivity" in reg

    # Compare recomputed v1 vs v0 CSV degree_hours_pct_change per scenario
    merged = analysis.pct_df.merge(
        v0_pct[["scenario_id", "degree_hours_pct_change"]],
        on="scenario_id",
        suffixes=("_v1", "_v0"),
    )
    np.testing.assert_allclose(
        merged["degree_hours_pct_change_v1"].values,
        merged["degree_hours_pct_change_v0"].values,
        rtol=1e-3,
        err_msg="degree_hours_pct_change mismatch vs v0",
    )

    # Slopes from v0 report (recomputed by v1 should match v0 CSV-derived regression)
    from scipy import stats

    valid = analysis.sensitivity_df.dropna(subset=["mean_albedo", "degree_hours_pct_change"])
    v0_valid = v0_sens.dropna(subset=["mean_albedo", "degree_hours_pct_change"])

    slope_v1, _, r_v1, _, _ = stats.linregress(
        valid["mean_albedo"], valid["degree_hours_pct_change"]
    )
    slope_v0, _, r_v0, _, _ = stats.linregress(
        v0_valid["mean_albedo"], v0_valid["degree_hours_pct_change"]
    )

    np.testing.assert_allclose(slope_v1, slope_v0, rtol=1e-3)
    np.testing.assert_allclose(r_v1**2, r_v0**2, rtol=1e-3)

    slope_e_v1, _, r_e_v1, _, _ = stats.linregress(
        valid["mean_emissivity"], valid["degree_hours_pct_change"]
    )
    slope_e_v0, _, r_e_v0, _, _ = stats.linregress(
        v0_valid["mean_emissivity"], v0_valid["degree_hours_pct_change"]
    )
    np.testing.assert_allclose(slope_e_v1, slope_e_v0, rtol=1e-3)
    np.testing.assert_allclose(r_e_v1**2, r_e_v0**2, rtol=1e-3)

    assert analysis.best_scenario == V0_BEST_SCENARIO
    assert analysis.worst_scenario == V0_WORST_SCENARIO

    np.testing.assert_allclose(analysis.best_pct_change, V0_BEST_PCT, rtol=1e-2, atol=0.5)
    np.testing.assert_allclose(analysis.worst_pct_change, V0_WORST_PCT, rtol=1e-2, atol=0.5)

    # Also check headline numbers vs paper targets
    np.testing.assert_allclose(reg["risk_albedo"]["slope"], V0_ALBEDO_SLOPE, rtol=0.02)
    assert reg["risk_albedo"]["r2"] >= 0.84
    np.testing.assert_allclose(reg["risk_emissivity"]["slope"], V0_EMISSIVITY_SLOPE, rtol=0.05)


@pytest.mark.slow
def test_slow_tier_full_pipeline_from_feathers(project_cfg):
    """Slow tier: full back-half from frozen feathers reproduces paper targets."""
    from treeheat.pipeline.biophysics import run_biophysical_scenarios

    raytracing_dir = get_path("raytracing_results_dir", project_cfg)
    if not raytracing_dir.exists():
        pytest.skip("Frozen raytracing feathers not available")

    results = run_biophysical_scenarios(cfg=project_cfg)
    analysis = run_analysis_pipeline(results, cfg=project_cfg, save_plots=False)
    reg = analysis.regression

    assert analysis.best_scenario == V0_BEST_SCENARIO
    assert analysis.worst_scenario == V0_WORST_SCENARIO

    albedo_slope = reg["risk_albedo"]["slope"]
    albedo_r2 = reg["risk_albedo"]["r2"]
    emissivity_slope = reg["risk_emissivity"]["slope"]

    assert 58.0 <= albedo_slope <= 64.1, f"albedo slope {albedo_slope} out of ±5% band"
    assert albedo_r2 >= 0.84, f"albedo R² {albedo_r2} below 0.84"
    assert -214 <= emissivity_slope <= -174, f"emissivity slope {emissivity_slope} out of ±10% band"

    assert abs(analysis.best_pct_change - V0_BEST_PCT) <= 2.0
    assert abs(analysis.worst_pct_change - V0_WORST_PCT) <= 3.0


@pytest.mark.slow
def test_runner_all_reproduces_acceptance_and_skips_rerun(project_cfg):
    """Orchestrated run all reproduces paper targets; second run skips completed work."""
    from treeheat.orchestration.runner import Runner

    config_path = _project_config()
    runner = Runner(cfg=project_cfg, config_path=config_path)

    report1 = runner.run(["raytrace", "biophysics", "analyze"])
    assert report1.ok
    assert len(report1.failed) == 0

    analysis_dir = get_path("analysis_results_dir", project_cfg)
    sensitivity = pd.read_csv(analysis_dir / "sensitivity_analysis.csv")
    from scipy import stats

    valid = sensitivity.dropna(subset=["mean_albedo", "degree_hours_pct_change"])
    slope_a, _, r_a, _, _ = stats.linregress(
        valid["mean_albedo"], valid["degree_hours_pct_change"]
    )
    slope_e, _, _, _, _ = stats.linregress(
        valid["mean_emissivity"], valid["degree_hours_pct_change"]
    )
    assert 58.0 <= slope_a <= 64.1
    assert r_a**2 >= 0.84
    assert -214 <= slope_e <= -174

    pct = pd.read_csv(analysis_dir / "pct_change_summary.csv")
    best = pct.loc[pct["degree_hours_pct_change"].idxmin()]
    worst = pct.loc[pct["degree_hours_pct_change"].idxmax()]
    assert best["scenario_id"] == V0_BEST_SCENARIO
    assert worst["scenario_id"] == V0_WORST_SCENARIO

    # Second full run should skip nearly everything
    report2 = runner.run(["raytrace", "biophysics", "analyze"])
    assert report2.ok
    total_skipped = len(report2.skipped) + len(report2.adopted)
    assert total_skipped >= 25  # at least all raytrace + biophysics scenarios


def test_weather_loader_epw(project_cfg):
    from treeheat.io.weather import find_warmest_day, load_epw

    df = load_epw(cfg=project_cfg)
    assert len(df) == 8760
    assert "Ta" in df.columns and "VPD" in df.columns

    day_of_year, hour_of_year, date = find_warmest_day(cfg=project_cfg)
    assert 0 <= day_of_year < 365
    assert 0 <= hour_of_year < 8760


def test_risk_metrics_on_sample():
    from treeheat.risk.metrics import calculate_stress_summary

    df = pd.DataFrame(
        {
            "tree_id": [1, 1, 1, 2, 2, 2],
            "T_leaf": [25.0, 32.0, 28.0, 29.0, 31.0, 27.0],
            "MRT": [22.0, 23.0, 22.5, 22.0, 23.0, 22.5],
            "Tsurf": [24.0, 25.0, 24.5, 24.0, 25.0, 24.5],
        }
    )
    summary = calculate_stress_summary(df, T_crit=30.0)
    assert len(summary) == 2
    assert summary.loc[summary["tree_id"] == 1, "heat_stress_hours"].iloc[0] == 1
    assert summary.loc[summary["tree_id"] == 1, "degree_hours"].iloc[0] == 2.0
