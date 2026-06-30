"""Capstone: external project populated from v0 archive inputs runs end-to-end."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from treeheat import api
from treeheat.config import reload_config
from treeheat.project import init_project, project_config_path, validate_project

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = REPO_ROOT / "src_archive"


def _archive_available() -> bool:
    return (ARCHIVE / "weather.epw").exists() and (ARCHIVE / "grid_records").is_dir()


@pytest.mark.slow
@pytest.mark.skipif(not _archive_available(), reason="v0 archive inputs not present")
def test_external_project_end_to_end(tmp_path: Path) -> None:
    """Generalization test: init external dir, populate per runbook, run biophysics+analyze."""
    project = tmp_path / "external_capstone"
    init_project(project)

    # Populate inputs as the runbook describes (simulating GH export)
    shutil.copy2(ARCHIVE / "weather.epw", project / "inputs" / "weather.epw")
    shutil.copy2(
        ARCHIVE / "grid_records" / "baseline_trees.csv",
        project / "inputs" / "grid_records" / "baseline_trees.csv",
    )
    shutil.copy2(
        ARCHIVE / "grid_records" / "jodla_scenario_grid.csv",
        project / "inputs" / "grid_records" / "scenario_sensor_grid.csv",
    )
    shutil.copy2(
        ARCHIVE / "grid_records" / "jodla_baseline_grid.csv",
        project / "inputs" / "grid_records" / "baseline_sensor_grid.csv",
    )
    shutil.copy2(
        ARCHIVE / "grid_records" / "baseline_materials.csv",
        project / "inputs" / "grid_records" / "baseline_materials.csv",
    )
    shutil.copy2(
        ARCHIVE / "grid_records" / "scenario_grid_materials.csv",
        project / "inputs" / "grid_records" / "scenario_grid_materials.csv",
    )
    shutil.copy2(
        ARCHIVE / "base_material_library.txt",
        project / "inputs" / "base_material_library.txt",
    )

    baseline_src = ARCHIVE / "python" / "baseline_radiance_project"
    scenario_src = ARCHIVE / "python" / "scenario_radiance_project"
    shutil.copytree(
        baseline_src,
        project / "inputs" / "radiance" / "baseline_radiance_project",
        dirs_exist_ok=True,
    )
    shutil.copytree(
        scenario_src,
        project / "inputs" / "radiance" / "scenario_radiance_project",
        dirs_exist_ok=True,
    )

    # Point raytracing at frozen v0 feathers (adopt path)
    ray_dir = project / "outputs" / "raytracing"
    ray_dir.mkdir(parents=True, exist_ok=True)
    v0_feathers = ARCHIVE / "raytracing_results"
    if v0_feathers.is_dir():
        for feather in v0_feathers.glob("*.feather"):
            shutil.copy2(feather, ray_dir / feather.name)

    cfg_path = project_config_path(project)
    report = validate_project(project, check_config=True)
    assert report.config_valid is True, report.config_error

    reload_config(cfg_path)
    run_report = api.run(["biophysics", "analyze"], config_path=cfg_path)
    assert run_report.ok, run_report.failed

    analysis = api.load_analysis(cfg_path)
    assert not analysis.pct_df.empty
    assert not analysis.sensitivity_df.empty

    state = api.status(cfg_path)
    assert "tasks" in state
    assert any(k.startswith("analyze:") for k in state["tasks"])
