# Phase 01 — Skeleton + config backbone

**Date:** 2026-06-29 16:00
**Phase:** 1 (skeleton + config)
**Inputs read:** `.agent/handoff/proposed_skeleton/`, `src_archive/config.yaml`, `src_archive/config_locator.py`, `.agent/local_memory/20260629-1535_phase00_roadmap.md`, approved Phase 1 plan.

---

## What was built

1. **v1 project tree** at top-level `treeheat/` — materialized from `proposed_skeleton/` with all stub modules preserved (config → io → radiance → physics → risk → viz layering intact).

2. **Config split**
   - `config/defaults.yaml` — full non-path param port from v0 (`physical_constants`, `model.ceb/species_defaults/risk/ground/soil`, `analysis`, `simulation`, `outputs`).
   - `config/config.yaml` — portable relative paths under `data/` and `outputs/`, plus light run overrides (`canopy_engine`, `period_type`).

3. **`treeheat/config.py`**
   - `get_config()` — deep-merge `defaults.yaml` ← `config.yaml`, cached singleton.
   - `get_path(key)` — resolves relative paths against config-file directory.
   - `validate_config()` — loud failures on missing sections/keys and missing input paths; creates output dirs.
   - `ConfigError`, `reload_config()` for tests.

4. **Lazy engine registry** — `physics/engines/__init__.py` imports concrete engines only inside `get_engine()` via `importlib`; `import treeheat` stays free of scipy/pyradiance/geopandas.

5. **Packaging**
   - `pyproject.toml` — light base deps (`pyyaml`, `numpy`, `pandas`, `pyarrow`); extras: `physics`, `radiance`, `geo`, `viz`, `ui`, `dev`.
   - `uv.lock` committed; README documents `uv sync --extra dev` workflow and OS-level prerequisites.

6. **Tests** — `conftest.py`, `test_config.py`, `test_imports.py`, `test_engines.py`; `test_acceptance.py` remains skipped (Phase 4).

---

## Key decisions

1. **Full param port in Phase 1** — all v0 model constants live in `defaults.yaml` now so `validate_config()` checks a real schema, not stubs.
2. **Light base install** — heavy deps isolated in optional extras; lazy engine imports enforce this at runtime.
3. **Path validation scope** — four required input paths (`weather_file`, species/material DBs, `grid_records_dir`); output dirs created, not required pre-existing.
4. **Shipped `config/config.yaml` paths** point at Phase 2 data locations; full validation of the shipped config will pass once Phase 2 copies inputs.

---

## Deviations from the plan

- Added `build-system` / hatchling config to `pyproject.toml` (required for `uv sync` editable install; not explicit in plan but necessary).
- Expanded `config/config.yaml` paths beyond the skeleton minimum (tree/sensor grid files, radiance project dirs) to match v0 schema for downstream phases.
- Bumped package version to `0.1.0` (plan implied first real milestone vs skeleton `0.0.0`).

---

## Test / acceptance status

```text
uv run pytest — 11 passed, 1 skipped (acceptance gate placeholder)
```

Phase 1 done criteria met:
- `import treeheat` succeeds without scipy/pyradiance/geopandas in `sys.modules`
- `validate_config()` passes on complete fixture; clear errors on missing key/path
- Engine registry resolves `li2023_ceb` and `legacy_leaf`

---

## Next step

**Phase 2** — copy reference data (two databases, grid records, weather, METHODOLOGY) into `treeheat/data/`; typed loaders with schema-conformance tests.
