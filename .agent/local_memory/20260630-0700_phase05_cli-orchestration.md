# Phase 05 — CLI + orchestration core

**Date:** 2026-06-30 07:00
**Phase:** 5 (config-driven entry point, orchestration core, thin API, v0 script decommission)
**Inputs read:** approved Phase 5 plan, v0 `run_analysis.py` / `material_scenario_workflow.py`, handoff §3 + Rec. 1, Phases 0–4 memory.

---

## What was built

1. **Orchestration package** — [treeheat/treeheat/orchestration/](treeheat/treeheat/orchestration/):
   - `jobspec.py` — `JobSpec.from_config()` validates 25 scenarios, engine, period
   - `hashing.py` — file/config/content fingerprints + code version
   - `provenance.py` — JSON sidecars under `outputs/provenance/<stage>/`
   - `runstate.py` — atomic `outputs/run_state.json` (schema v1)
   - `runner.py` — skip-if-hash-matches, raytrace adopt-existing-feathers, per-task provenance

2. **Pipeline stages** — [treeheat/treeheat/pipeline/](treeheat/treeheat/pipeline/):
   - `biophysics.py` — added `run_biophysical_scenario()`, `load_biophysical_results()`
   - `raytrace.py` — v0 port: three-tier material selection, `RadianceProjectManager`, `run_scenario_raytrace()` (lazy pyradiance; not exercised by gate)

3. **CLI** — [treeheat/treeheat/cli.py](treeheat/treeheat/cli.py): `run {raytrace|biophysics|analyze|all}`, `--force`, `--scenarios`, `status` (JSON)

4. **Python API** — [treeheat/treeheat/api.py](treeheat/treeheat/api.py): `run()`, `status()`, `load_analysis()`; re-exported from `treeheat/__init__.py`

5. **v0 decommission** — [`.agent/handoff/06_retired_scripts.md`](.agent/handoff/06_retired_scripts.md) (read-only archive preserved; mapping to v1 entry points)

6. **Tests** — [treeheat/tests/test_orchestration.py](treeheat/tests/test_orchestration.py) + slow runner acceptance in [treeheat/tests/test_acceptance.py](treeheat/tests/test_acceptance.py)

---

## Key decisions

1. **Raytrace adopt path** — frozen v0 feathers in read-only `src_archive/raytracing_results` are recorded `done` with provenance without invoking Radiance (gate path for `run all`).
2. **Provenance central dir** — `outputs/provenance/` avoids writing sidecars next to read-only archive inputs.
3. **25-scenario order** — regression test locks `simulation.instructions` to v0 `config.yaml` order (facade outer, landscape inner), not `workflow_analysis.py`'s ad-hoc loop nesting.
4. **Retire = document** — v0 scripts stay in read-only `src_archive/` per AGENTS.md.

---

## Deviations from the plan

- Fixed matplotlib 3.14 `boxplot(tick_labels=...)` in [treeheat/treeheat/viz/plots.py](treeheat/treeheat/viz/plots.py) (surfaced when runner enabled `save_plots=True` on analyze).
- Added `get_config_path()` to [treeheat/treeheat/config.py](treeheat/treeheat/config.py) for runner provenance.

---

## Test / acceptance status

```text
uv run pytest -m "not slow"  — 36 passed, 3 deselected
uv run pytest -m slow        — 3 passed (~67s)
uv run treeheat run all      — 51 tasks skipped on re-run (~1.7s)
uv run treeheat status       — machine-readable JSON at outputs/run_state.json
```

### Done criteria: **PASS**

| Criterion | Result |
|-----------|--------|
| `treeheat run all` reproduces acceptance | PASS (slow runner test) |
| Re-run skips completed scenarios | PASS (51 skipped: 25 raytrace + 25 biophysics + analyze) |
| Every output carries provenance | PASS (`outputs/provenance/<stage>/*.json`) |
| Run-state machine-readable | PASS (`outputs/run_state.json`, schema v1) |

---

## Next step

Phase 6 per roadmap — data-retention decision (Rec. 5), or Stage 2→3 automation spike; UI skin remains last (Rec. 7).
