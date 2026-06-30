# Phase 03 — Physics behind the canopy engine interface

**Date:** 2026-06-29 18:15
**Phase:** 3 (physics + pluggable engines)
**Inputs read:** approved Phase 3 plan, v0 integrator/engines/physics modules, Phase 0–2 memory, existing v1 skeleton.

---

## What was built

1. **`CanopyEngine` interface** — [treeheat/treeheat/physics/engines/base.py](treeheat/treeheat/physics/engines/base.py): `CanopyState` (superset of CEB + legacy inputs), `CanopyResult`, abstract `solve()`.

2. **Species adapter** — [treeheat/treeheat/physics/species_params.py](treeheat/treeheat/physics/species_params.py): `SpeciesParams` from `SpeciesRecord` + `config.model.species_defaults`; Jarvis `fRad/fVPD/fSM/fT` ported from v0 `TreeSpecies`.

3. **Physics modules** (dict-config, no hardcoded constants):
   - [physics/ground.py](treeheat/treeheat/physics/ground.py) — `GroundEnergyBalance`, `GroundState`, `get_ground_type_from_material`
   - [physics/surface.py](treeheat/treeheat/physics/surface.py) — `calculate_surface_temperature`, `calculate_mrt`, `calculate_longwave_in`
   - [physics/soil_moisture.py](treeheat/treeheat/physics/soil_moisture.py) — `SoilMoistureBucket`, `SoilMoistureState`
   - [radiance/upwelling.py](treeheat/treeheat/radiance/upwelling.py) — `calculate_upwelling`, `extract_grid_id_from_column`
   - [io/grids.py](treeheat/treeheat/io/grids.py) — minimal grid-material mapping loaders

4. **Canopy engines**
   - [physics/engines/li2023_ceb.py](treeheat/treeheat/physics/engines/li2023_ceb.py) — default; full Li2023 CEB port
   - [physics/engines/legacy_leaf.py](treeheat/treeheat/physics/engines/legacy_leaf.py) — legacy cross-check; internal `Kabs`/`L_in`/`Rn` pre-compute

5. **Integrator** — [physics/integrator.py](treeheat/treeheat/physics/integrator.py): `solve_tree_hour()` (ground → soil → surface → `get_engine(config)` → soil update); `run_biophysics()` thin loop. No concrete engine imports.

6. **Tests** — [tests/test_physics_engines.py](treeheat/tests/test_physics_engines.py): v0-vs-v1 differential CEB chain; one-line engine swap; integrator import guard.

---

## Key decisions

1. **Design around CEB, adapt legacy** — `CanopyState` carries a superset of raw fields; legacy engine computes its own radiation (`Kabs`, `L_in`, `Rn`) internally so the integrator never branches on engine type.
2. **fSM thresholds** — v0 `TreeSpecies.fSM` referenced `model.risk.theta_crit/theta_wilt` (absent in v0 config); v1 maps to `model.soil.theta_fc` / `theta_wilt`.
3. **Config values** — v1 `defaults.yaml` already matched `src_archive/config.yaml` from Phase 1; no param drift found.
4. **Lazy registry preserved** — `import treeheat` still avoids scipy; engines load on `get_engine()`.

---

## Deviations from the plan

- None on scope. `run_biophysics()` is intentionally thin (plan allowed; full EPW/feather/scenario IO deferred to Phase 4).

---

## Test / acceptance status

```text
uv run pytest — 25 passed, 1 skipped (acceptance gate placeholder)
```

Phase 3 done criteria met:
- Single-tree/single-hour CEB solve matches v0 chain (`T_leaf`, `H`, `LE`, `Kabs`, `Rn` within 1e-6)
- `legacy_leaf` runs via `engine_name=` / config swap only
- Integrator imports `get_engine` only, not concrete models

---

## Next step

**Phase 4** — radiance runner, risk metrics, cross-scenario analysis, frozen-feather acceptance gate.
