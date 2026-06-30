"""Tests for orchestration core: hashing, run-state, skip/adopt, config grid."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from treeheat.config import get_config, reload_config
from treeheat.orchestration.hashing import config_sha256, content_hash, file_fingerprint
from treeheat.orchestration.jobspec import JobSpec
from treeheat.orchestration.runstate import RunState, task_key
from treeheat.orchestration.runner import Runner
from treeheat.pipeline.raytrace import raytrace_outputs_exist


def _project_config() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "config.yaml"


@pytest.fixture(scope="module")
def project_cfg():
    config_path = _project_config()
    if not config_path.exists():
        pytest.skip("Project config not found")
    reload_config(config_path)
    return get_config(config_path)


def test_simulation_instructions_match_5x5_grid(project_cfg):
    """Preserves the 25-scenario 5x5 naturalness grid (v0 config.yaml order)."""
    instructions = project_cfg["simulation"]["instructions"]
    ratios = [0.0, 0.25, 0.5, 0.75, 1.0]
    expected_set = {(float(la), float(fa)) for la in ratios for fa in ratios}
    actual_set = {(float(i[0]), float(i[1])) for i in instructions}
    assert len(instructions) == 25
    assert actual_set == expected_set
    assert project_cfg["simulation"]["n_scenarios"] == 25
    # v0 canonical order: landscape sweeps at fixed facade (matches src_archive/config.yaml)
    expected_order = [
        [la, fa] for fa in ratios for la in ratios
    ]
    assert instructions == expected_order


def test_jobspec_from_config(project_cfg):
    job = JobSpec.from_config(project_cfg, ["biophysics", "analyze"])
    assert len(job.scenarios) == 25
    assert job.engine == "li2023_ceb"
    assert job.period == "warmest_week"
    assert job.scenarios[0].scenario_id == "scenario_000"
    assert job.scenarios[12].instruction == (0.5, 0.5)


def test_content_hash_stable(project_cfg):
    h1 = content_hash("biophysics", "scenario_000", {"model": {"x": 1}}, {"a": "fp1"})
    h2 = content_hash("biophysics", "scenario_000", {"model": {"x": 1}}, {"a": "fp1"})
    h3 = content_hash("biophysics", "scenario_001", {"model": {"x": 1}}, {"a": "fp1"})
    assert h1 == h2
    assert h1 != h3


def test_file_fingerprint_missing(tmp_path):
    assert file_fingerprint(tmp_path / "nope.txt").startswith("missing:")


def test_runstate_round_trip(tmp_path, project_cfg):
    path = tmp_path / "run_state.json"
    state = RunState.create(_project_config(), project_cfg)
    key = task_key("biophysics", "scenario_000")
    state.mark_done(key, "abc123", [tmp_path / "out.csv"])
    state.save(path)

    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == 1
    assert "tasks" in loaded
    assert loaded["tasks"][key]["status"] == "done"
    assert loaded["tasks"][key]["content_hash"] == "abc123"

    restored = RunState.load(path)
    assert restored.is_satisfied(key, "abc123")
    assert not restored.is_satisfied(key, "other")


def test_config_sha256_stable(project_cfg):
    assert config_sha256(project_cfg) == config_sha256(project_cfg)


def test_raytrace_adopt_frozen_feathers(project_cfg):
    """Raytrace stage adopts existing v0 feather pairs without compute."""
    from treeheat.config import get_path

    ray_dir = get_path("raytracing_results_dir", project_cfg)
    if not raytrace_outputs_exist(ray_dir, "scenario_000"):
        pytest.skip("Frozen feathers not available")

    config_path = _project_config()
    runner = Runner(cfg=project_cfg, config_path=config_path)
    report = runner.run(["raytrace"], scenario_ids=["scenario_000"])
    assert "raytrace:scenario_000" in report.adopted or "raytrace:scenario_000" in report.skipped


@pytest.mark.slow
def test_biophysics_skip_on_rerun(project_cfg):
    """Second biophysics run skips completed scenario (content-addressed)."""
    config_path = _project_config()
    runner = Runner(cfg=project_cfg, config_path=config_path)
    sid = ["scenario_000"]

    report1 = runner.run(["biophysics"], scenario_ids=sid, force=True)
    assert "biophysics:scenario_000" in report1.completed

    report2 = runner.run(["biophysics"], scenario_ids=sid, force=False)
    assert "biophysics:scenario_000" in report2.skipped


def test_task_key_format():
    assert task_key("analyze") == "analyze:all"
    assert task_key("raytrace", "scenario_012") == "raytrace:scenario_012"
