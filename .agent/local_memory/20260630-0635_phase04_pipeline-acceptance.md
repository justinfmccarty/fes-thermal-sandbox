# Phase 04 — Back-half pipeline + acceptance gate

**Date:** 2026-06-30 06:35
**Phase:** 4 (radiance runner, risk, analysis, plots, end-to-end sweep, acceptance test)
**Inputs read:** approved Phase 4 plan, v0 archive modules, Phase 0–3 memory, frozen v0 feathers + analysis_outputs.

---

## What was built

1. **Config paths** — [treeheat/config/config.yaml](treeheat/config/config.yaml): frozen v0 inputs read from `src_archive/` (read-only); `v0_reference_dir` added for fast-tier ground truth; outputs under `treeheat/outputs/`.

2. **Weather loader** — [treeheat/treeheat/io/weather.py](treeheat/treeheat/io/weather.py): `load_epw`, `find_warmest_day`, `get_week_around_day`, VPD/qa/L_sky derivation (byte-for-byte port from v0).

3. **Risk metrics** — [treeheat/treeheat/risk/metrics.py](treeheat/treeheat/risk/metrics.py): degree-hours, heat-stress hours, extended summary with MRT/Tsurf.

4. **Scenario driver** — [treeheat/treeheat/pipeline/biophysics.py](treeheat/treeheat/pipeline/biophysics.py): `BiophysicalScenarioRunner` + `run_biophysical_scenarios()` — tree→sensor mapping, material cache, upwelling, warmest-week slice; delegates per-tree-hour physics to `integrator.solve_tree_hour`; asserts grid==feather column count.

5. **Cross-scenario analysis** — [treeheat/treeheat/risk/analysis.py](treeheat/treeheat/risk/analysis.py): pct-change vs scenario_012, area-weighted albedo/emissivity, linregress sensitivity, report + CSV outputs, `run_analysis_pipeline()`.

6. **Plots** — [treeheat/treeheat/viz/plots.py](treeheat/treeheat/viz/plots.py): heatmap, sensitivity curves, concept diagram, box/bar charts.

7. **Radiance runner** — [treeheat/treeheat/radiance/runner.py](treeheat/treeheat/radiance/runner.py): faithful port of v0 2-phase DDS with lazy `pyradiance` import (optional extra).

8. **CLI** — [treeheat/treeheat/cli.py](treeheat/treeheat/cli.py): `treeheat run {raytrace|biophysics|analyze|all}` wired to pipeline modules.

9. **Acceptance test** — [treeheat/tests/test_acceptance.py](treeheat/tests/test_acceptance.py): two-tier gate (fast: analysis on frozen v0 CSVs; slow: full feathers→biophysics→analysis).

---

## Key decisions

1. **Frozen feathers from src_archive** — no 500 MB duplication; config points at read-only archive paths.
2. **Two-tier acceptance** — fast tier isolates analysis math (rtol=1e-3); slow tier validates full physics chain with ±5%/±10% slope bands.
3. **scipy in core deps** — required by analysis + integrator; moved from optional `physics` extra.
4. **Default species** — trees without species column use `default_species_params()` (matches v0 `get_species('default')`).

---

## Deviations from the plan

- None on scope. Slow-tier numbers matched v0 **exactly** (not just within tolerance bands) — no physics drift detected in the warmest-week sweep.

---

## Test / acceptance status

```text
uv run pytest -m "not slow"  — 28 passed, 1 deselected
uv run pytest -m slow        — 1 passed (69s)
```

### Acceptance gate result: **PASS**

| Metric | Target (v0 paper) | v1 slow-tier actual | Tolerance | Result |
|--------|-------------------|---------------------|-----------|--------|
| Risk vs albedo slope | +61.04 %/unit | **+61.04 %/unit** | ±5% (58.0–64.1) | PASS |
| Risk vs albedo R² | 0.871 | **0.871** | ≥ 0.84 | PASS |
| Risk vs emissivity slope | -194.21 %/unit | **-194.21 %/unit** | ±10% (-174 to -214) | PASS |
| Best scenario | scenario_004 (~ -5.21%) | **scenario_004 (-5.21%)** | identity + ±2.0 abs pts | PASS |
| Worst scenario | scenario_020 (~ +12.76%) | **scenario_020 (+12.76%)** | identity + ±3.0 abs pts | PASS |

Fast tier: v1 analysis recomputed from frozen v0 biophysical CSVs matches v0 `sensitivity_analysis.csv` and `pct_change_summary.csv` within rtol=1e-3.

---

## Next step

**Phase 5** — workflow UI (thin Streamlit skin over orchestration core) or front-end geometry pipeline (photogrammetry → Rhino), per roadmap.
