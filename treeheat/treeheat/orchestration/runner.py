"""Orchestration runner — skip-already-computed, provenance, run-state."""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from treeheat.config import get_config, get_config_path, get_path
from treeheat.orchestration.hashing import config_sha256, content_hash, file_fingerprint
from treeheat.orchestration.jobspec import JobSpec, ScenarioSpec
from treeheat.orchestration.provenance import Provenance, write_provenance
from treeheat.orchestration.runstate import RunState, task_key
from treeheat.pipeline.biophysics import (
    BiophysicalScenarioRunner,
    biophysical_output_path,
    load_biophysical_results,
    run_biophysical_scenario,
)
from treeheat.pipeline.raytrace import (
    raytrace_feather_paths,
    raytrace_outputs_exist,
    run_scenario_raytrace,
)
from treeheat.risk.analysis import run_analysis_pipeline

__all__ = ["RunReport", "Runner", "outputs_root_from_config"]

STAGE_ORDER = ("raytrace", "biophysics", "analyze")


def outputs_root_from_config(cfg: dict[str, Any]) -> Path:
    """Root outputs directory (parent of biophysical_outputs_dir)."""
    return get_path("biophysical_outputs_dir", cfg).parent


@dataclass
class RunReport:
    stages: list[str]
    completed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    adopted: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.failed) == 0


class Runner:
    """Builds scenario task graph, skips completed work, writes provenance + run-state."""

    def __init__(
        self,
        cfg: dict[str, Any] | None = None,
        config_path: Path | str | None = None,
    ):
        if cfg is None:
            cfg = get_config(config_path)
        self.cfg = cfg
        self.config_path = Path(config_path) if config_path else _infer_config_path()
        self.outputs_root = outputs_root_from_config(cfg)
        self.biophysical_dir = get_path("biophysical_outputs_dir", cfg)
        self.analysis_dir = get_path("analysis_results_dir", cfg)
        self.raytracing_dir = get_path("raytracing_results_dir", cfg)
        self.run_state_path = self.outputs_root / "run_state.json"
        self._biophysical_runner: BiophysicalScenarioRunner | None = None

    def _get_biophysical_runner(self) -> BiophysicalScenarioRunner:
        if self._biophysical_runner is None:
            self._biophysical_runner = BiophysicalScenarioRunner(self.cfg)
        return self._biophysical_runner

    def load_run_state(self) -> RunState:
        state = RunState.load(self.run_state_path)
        if not state.config_path:
            state = RunState.create(self.config_path, self.cfg)
        return state

    def run(
        self,
        stages: list[str],
        scenario_ids: list[str] | None = None,
        force: bool = False,
    ) -> RunReport:
        ordered = [s for s in STAGE_ORDER if s in stages]
        if not ordered:
            raise ValueError(f"No valid stages in {stages!r}. Expected subset of {STAGE_ORDER}")

        job = JobSpec.from_config(self.cfg, ordered, scenario_ids)
        state = self.load_run_state()
        state.config_path = str(self.config_path)
        state.config_sha256 = config_sha256(self.cfg)
        report = RunReport(stages=ordered)

        biophysical_results: dict[str, Any] = {}

        for stage in ordered:
            if stage == "raytrace":
                self._run_raytrace_stage(job, state, report, force)
            elif stage == "biophysics":
                biophysical_results = self._run_biophysics_stage(job, state, report, force)
            elif stage == "analyze":
                self._run_analyze_stage(job, state, report, force, biophysical_results)

        state.save(self.run_state_path)
        return report

    def _run_raytrace_stage(
        self,
        job: JobSpec,
        state: RunState,
        report: RunReport,
        force: bool,
    ) -> None:
        cfg_subset = {
            "simulation": self.cfg.get("simulation", {}),
            "paths": {
                "baseline_project_dir": str(get_path("baseline_project_dir", self.cfg)),
                "scenario_project_dir": str(get_path("scenario_project_dir", self.cfg)),
            },
        }

        for scenario in job.scenarios:
            key = task_key("raytrace", scenario.scenario_id)
            direct, diffuse = raytrace_feather_paths(self.raytracing_dir, scenario.scenario_id)
            input_fps = {
                "baseline_project": file_fingerprint(get_path("baseline_project_dir", self.cfg)),
                "scenario_project": file_fingerprint(get_path("scenario_project_dir", self.cfg)),
            }
            chash = content_hash(
                "raytrace",
                scenario.scenario_id,
                {**cfg_subset, "instruction": list(scenario.instruction)},
                input_fps,
            )

            if not force and state.is_satisfied(key, chash):
                report.skipped.append(key)
                continue

            outputs = [direct, diffuse]
            if raytrace_outputs_exist(self.raytracing_dir, scenario.scenario_id) and not force:
                self._record_done(
                    state, key, chash, outputs, "raytrace", scenario.scenario_id, input_fps
                )
                report.adopted.append(key)
                continue

            state.mark_running(key, chash)
            state.save(self.run_state_path)
            try:
                out_paths = run_scenario_raytrace(
                    scenario.scenario_id,
                    scenario.instruction,
                    self.cfg,
                    force=force,
                )
                self._record_done(
                    state, key, chash, out_paths, "raytrace", scenario.scenario_id, input_fps
                )
                report.completed.append(key)
            except Exception as exc:
                err = f"{exc}\n{traceback.format_exc()}"
                state.mark_failed(key, chash, err)
                report.failed.append(key)
                state.save(self.run_state_path)
                raise

            state.save(self.run_state_path)

    def _run_biophysics_stage(
        self,
        job: JobSpec,
        state: RunState,
        report: RunReport,
        force: bool,
    ) -> dict:
        runner = self._get_biophysical_runner()
        cfg_subset = {
            "model": self.cfg.get("model", {}),
            "analysis": self.cfg.get("analysis", {}),
        }
        results: dict = {}

        for scenario in job.scenarios:
            key = task_key("biophysics", scenario.scenario_id)
            direct, diffuse = raytrace_feather_paths(self.raytracing_dir, scenario.scenario_id)
            out_path = biophysical_output_path(self.biophysical_dir, scenario.scenario_id)
            input_fps = {
                "direct_feather": file_fingerprint(direct),
                "diffuse_feather": file_fingerprint(diffuse),
                "weather": file_fingerprint(get_path("weather_file", self.cfg)),
            }
            chash = content_hash(
                "biophysics",
                scenario.scenario_id,
                cfg_subset,
                input_fps,
            )

            if not force and state.is_satisfied(key, chash) and out_path.exists():
                report.skipped.append(key)
                results[scenario.scenario_id] = pd.read_csv(out_path)
                continue

            state.mark_running(key, chash)
            state.save(self.run_state_path)
            try:
                results_df, written = run_biophysical_scenario(
                    scenario.scenario_id,
                    runner,
                    self.cfg,
                    self.biophysical_dir,
                    raytracing_dir=self.raytracing_dir,
                )
                results[scenario.scenario_id] = results_df
                self._record_done(
                    state, key, chash, [written], "biophysics", scenario.scenario_id, input_fps
                )
                report.completed.append(key)
            except Exception as exc:
                err = f"{exc}\n{traceback.format_exc()}"
                state.mark_failed(key, chash, err)
                report.failed.append(key)
                state.save(self.run_state_path)
                raise

            state.save(self.run_state_path)

        return results

    def _run_analyze_stage(
        self,
        job: JobSpec,
        state: RunState,
        report: RunReport,
        force: bool,
        biophysical_results: dict,
    ) -> None:
        key = task_key("analyze")
        cfg_subset = {"analysis": self.cfg.get("analysis", {})}

        scenario_ids = [s.scenario_id for s in job.scenarios]
        if not biophysical_results:
            biophysical_results = load_biophysical_results(
                self.cfg, scenario_ids, self.biophysical_dir
            )
        if not biophysical_results:
            raise RuntimeError(
                "No biophysical results for analyze stage. Run biophysics first."
            )

        input_fps = {
            f"bio_{sid}": file_fingerprint(
                biophysical_output_path(self.biophysical_dir, sid)
            )
            for sid in sorted(biophysical_results.keys())
        }
        chash = content_hash("analyze", None, cfg_subset, input_fps)

        if not force and state.is_satisfied(key, chash):
            report.skipped.append(key)
            return

        state.mark_running(key, chash)
        state.save(self.run_state_path)
        try:
            analysis = run_analysis_pipeline(
                biophysical_results,
                cfg=self.cfg,
                output_dir=self.analysis_dir,
                save_plots=self.cfg.get("outputs", {}).get("save_plots", True),
            )
            outputs = [
                self.analysis_dir / "stress_summary_all_scenarios.csv",
                self.analysis_dir / "pct_change_summary.csv",
                self.analysis_dir / "sensitivity_analysis.csv",
                self.analysis_dir / "analysis_report.md",
            ]
            self._record_done(state, key, chash, outputs, "analyze", None, input_fps)
            report.completed.append(key)
            self._last_analysis = analysis
        except Exception as exc:
            err = f"{exc}\n{traceback.format_exc()}"
            state.mark_failed(key, chash, err)
            report.failed.append(key)
            state.save(self.run_state_path)
            raise

        state.save(self.run_state_path)

    def _record_done(
        self,
        state: RunState,
        key: str,
        chash: str,
        outputs: list[Path | str],
        stage: str,
        scenario_id: str | None,
        input_fps: dict[str, str],
    ) -> None:
        state.mark_done(key, chash, outputs)
        prov = Provenance.build(
            stage=stage,
            scenario_id=scenario_id,
            canopy_engine=self.cfg.get("model", {}).get("canopy_engine", "li2023_ceb"),
            content_hash=chash,
            config_path=self.config_path,
            config_sha256=config_sha256(self.cfg),
            input_fingerprints=input_fps,
            output_paths=[str(p) for p in outputs],
        )
        write_provenance(prov, self.outputs_root)


def _infer_config_path() -> Path:
    path = get_config_path()
    if path is not None:
        return path
    return Path.cwd() / "config" / "config.yaml"
