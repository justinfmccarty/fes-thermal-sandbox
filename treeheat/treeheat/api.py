"""Thin Python API for notebooks and the future UI skin.

Depends only on orchestration + config — not on pipeline modules directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from treeheat.config import get_config, reload_config, validate_config
from treeheat.orchestration.runner import RunReport, Runner
from treeheat.risk.analysis import AnalysisResults, run_analysis_pipeline

__all__ = ["load_analysis", "run", "status", "available_canopy_engines"]

STAGE_ALIASES = {
    "all": ["raytrace", "biophysics", "analyze"],
}


def _resolve_config(config_path: str | Path | None) -> Path:
    if config_path is None:
        candidate = Path.cwd() / "config" / "config.yaml"
        if not candidate.exists():
            raise FileNotFoundError("config/config.yaml not found; pass config_path explicitly")
        return candidate.resolve()
    path = Path(config_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def available_canopy_engines() -> list[str]:
    """Registered canopy engine names (for UI / project setup)."""
    from treeheat.physics.engines import registered_engine_names

    return registered_engine_names()


def run(
    stages: str | list[str],
    config_path: str | Path | None = None,
    scenarios: list[str] | None = None,
    force: bool = False,
) -> RunReport:
    """Run pipeline stage(s). stages may be 'all' or a list like ['biophysics', 'analyze']."""
    cfg_path = _resolve_config(config_path)
    reload_config(cfg_path)
    cfg = get_config(cfg_path)
    validate_config(cfg, config_dir=cfg_path.parent)

    if isinstance(stages, str):
        stage_list = STAGE_ALIASES.get(stages, [stages])
    else:
        stage_list = list(stages)

    runner = Runner(cfg=cfg, config_path=cfg_path)
    return runner.run(stage_list, scenario_ids=scenarios, force=force)


def status(config_path: str | Path | None = None) -> dict[str, Any]:
    """Return parsed run-state dict (empty structure if no run yet)."""
    cfg_path = _resolve_config(config_path)
    reload_config(cfg_path)
    cfg = get_config(cfg_path)
    runner = Runner(cfg=cfg, config_path=cfg_path)
    state = runner.load_run_state()
    if runner.run_state_path.exists():
        return json.loads(runner.run_state_path.read_text(encoding="utf-8"))
    return state.to_dict()


def load_analysis(config_path: str | Path | None = None) -> AnalysisResults:
    """Load analysis outputs from disk and wrap as AnalysisResults."""
    cfg_path = _resolve_config(config_path)
    reload_config(cfg_path)
    cfg = get_config(cfg_path)
    from treeheat.config import get_path
    from treeheat.pipeline.biophysics import load_biophysical_results

    analysis_dir = get_path("analysis_results_dir", cfg)
    biophysical = load_biophysical_results(cfg)

    master = pd.read_csv(analysis_dir / "stress_summary_all_scenarios.csv")
    pct = pd.read_csv(analysis_dir / "pct_change_summary.csv")
    sensitivity = pd.read_csv(analysis_dir / "sensitivity_analysis.csv")

    return AnalysisResults(
        master_summary=master,
        pct_df=pct,
        sensitivity_df=sensitivity,
        biophysical_results=biophysical,
    )
