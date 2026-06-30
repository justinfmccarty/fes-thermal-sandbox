# Feature — generate scenario grid materials (unblock biophysics)

**Date:** 2026-06-30 15:45
**Scope:** follow-up to Phase 8 (user ran 8 scenarios, biophysics failed)

## Symptom

```
ValueError: No material assignments found for scenario: scenario_000
  io/grids.py get_grid_materials_for_scenario  ← upwelling ← biophysics
```

`inputs/grid_records/scenario_grid_materials.csv` was only a header. Biophysics'
upwelling term needs, per scenario, the material at each sensor-grid point (to look up
albedo), keyed `scenario_id, grid_id, material_name`.

## Root cause

v0 generated this file with `src_archive/populate_scenario_materials.py`
(baseline grid materials + scenario instructions + naturalness three-tier coverage, same
md5 seed as the raytrace swap). That step was **never ported to v1** — the capstone/
acceptance tests just *copy* a pre-made file from the archive, so the gap was invisible.
A fresh external project therefore has no scenario grid materials and biophysics dies.

## Changes

New `treeheat/pipeline/grid_materials.py` (port of the v0 script, config-driven):
- `build_scenario_grid_materials(cfg)` — reads `grid_material_mapping_file`
  (`baseline_materials.csv`), builds the `NaturalnessMaterialCatalog`
  (material DB + base library), and for each `simulation.instructions[i]` →
  `scenario_{i:03d}` assigns ground/facade grids via the **same** seeded three-tier
  coverage as `raytrace.apply_material_scenario`. Emits baseline + all scenario rows.
- `write_scenario_grid_materials(cfg)` — writes the CSV to `scenario_grid_materials_file`.
- `scenario_rows_present(cfg)` — True if the file already has non-baseline rows.

Integration:
- `pipeline/biophysics.py::BiophysicalScenarioRunner.__init__` now auto-generates the
  file (with a printed note) when `scenario_rows_present` is False, before loading the
  mapping. Makes biophysics run with no extra manual step.
- `cli.py`: new `treeheat materials --config ...` to generate explicitly.
- Runbook (packaged + docs copies): Step 5 now states scenario materials are *generated*
  (auto, or `treeheat materials`); fixed baseline column name to `ground_or_facade`
  (was wrongly documented as `surface_type`).

## Verification

- Ran `treeheat materials` on the real kings-road project → wrote 2496 rows, 25 scenarios.
  `scenario_000` (target 0,0 = least natural) = 65 ground grids `grey_asphalt` + 31 facade
  grids `glass`, matching the baseline ground/facade split and the least-natural picks.
- Full suite: **47 passed** (capstone supplies its own file so auto-gen no-ops there;
  acceptance reproduction unchanged — auto-gen only fires when scenario rows are absent).

## Notes / deviations

- Generation lives in `pipeline/` (not `io/`) because it needs the raytrace catalog;
  `build_*` imports the catalog lazily to keep the boundary clean.
- Generates rows for *all* config instructions (25 if the full grid), which is a superset
  of whatever subset was raytraced — biophysics only reads the scenarios it runs.
- Did not add a dedicated unit test (no baseline_materials fixture in conftest; behavior
  is covered end-to-end by the real-project run + full suite). Revisit if formalized.
