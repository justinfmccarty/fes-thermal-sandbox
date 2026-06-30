"""Validated job specification derived from config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from treeheat.physics.engines import registered_engine_names

__all__ = ["JobSpec", "ScenarioSpec"]

VALID_PERIODS = frozenset({"annual", "warmest_week"})


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    landscape_ratio: float
    facade_ratio: float

    @property
    def instruction(self) -> tuple[float, float]:
        return (self.landscape_ratio, self.facade_ratio)


@dataclass
class JobSpec:
    scenarios: list[ScenarioSpec]
    period: str
    engine: str
    stages: list[str]

    @classmethod
    def from_config(
        cls,
        cfg: dict[str, Any],
        stages: list[str],
        scenario_ids: list[str] | None = None,
    ) -> JobSpec:
        sim = cfg.get("simulation", {})
        analysis = cfg.get("analysis", {})
        model = cfg.get("model", {})

        instructions = sim.get("instructions", [])
        n_scenarios = int(sim.get("n_scenarios", len(instructions)))
        if len(instructions) != n_scenarios:
            raise ValueError(
                f"simulation.instructions has {len(instructions)} entries but "
                f"n_scenarios={n_scenarios}"
            )

        engine = model.get("canopy_engine", "li2023_ceb")
        known = registered_engine_names()
        if engine not in known:
            raise ValueError(f"Unknown canopy_engine {engine!r}. Known: {known}")

        period = analysis.get("period_type", "warmest_week")
        if period not in VALID_PERIODS:
            raise ValueError(f"analysis.period_type must be one of {sorted(VALID_PERIODS)}")

        all_scenarios = [
            ScenarioSpec(
                scenario_id=f"scenario_{idx:03d}",
                landscape_ratio=float(instr[0]),
                facade_ratio=float(instr[1]),
            )
            for idx, instr in enumerate(instructions)
        ]

        if scenario_ids is not None:
            id_set = set(scenario_ids)
            filtered = [s for s in all_scenarios if s.scenario_id in id_set]
            missing = id_set - {s.scenario_id for s in filtered}
            if missing:
                raise ValueError(f"Unknown scenario ids: {sorted(missing)}")
            all_scenarios = filtered

        return cls(
            scenarios=all_scenarios,
            period=period,
            engine=engine,
            stages=list(stages),
        )
