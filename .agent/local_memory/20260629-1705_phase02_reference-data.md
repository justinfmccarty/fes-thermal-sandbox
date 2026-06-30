# Phase 02 — Reference data into v1

**Date:** 2026-06-29 17:05
**Phase:** 2 (reference data)
**Inputs read:** `src_archive/tree_species_database.csv`, `src_archive/root_material_database.csv`, `src_archive/METHODOLOGY.md`, `.agent/handoff/02_codebase_guide.md` §4, Phase 0/1 memory, approved Phase 2 plan.

---

## What was built

1. **Data placement** — verbatim copies into `treeheat/data/`:
   - `tree_species_database.csv` (33 species rows)
   - `root_material_database.csv` (15 material rows)

2. **Methodology reference** — `treeheat/docs/methodology.md` points at authoritative
   `src_archive/METHODOLOGY.md` (not duplicated); section map to v1 modules.

3. **Typed loaders**
   - `treeheat/io/schema.py` — `SchemaError`, `ColumnSpec`, `validate_dataframe`, parsers
   - `treeheat/io/species.py` — `SPECIES_SCHEMA`, `SpeciesRecord`, `SpeciesDatabase`,
     `load_species_database()` with dual-key lookup (species + common_name)
   - `treeheat/io/materials.py` — `MATERIAL_SCHEMA`, `MaterialRecord`, `MaterialDatabase`,
     `load_material_database()` with v0 accessors (`get_albedo`, `get_emissivity`, `get_naturalness`)
   - Exported from `treeheat/io/__init__.py`

4. **Schema-conformance tests** — `tests/test_reference_data.py` (11 tests) against shipped CSVs.

5. **Docs** — updated `treeheat/data/README.md` (correct row counts, ground-type note).

---

## Key decisions

1. **No pandera** — lightweight schema spec in code drives loader + test (base deps only).
2. **CSV schemas unchanged** — column names, order, and cell values preserved verbatim.
3. **Blank material thermal columns** — `heat_capacity_J_m2_K`, `evap_factor`, `k_drain` stay
   nullable; documented as superseded by `config.model.ground.types[ground_type]`.
4. **Engine param mapping deferred** — `SpeciesRecord` is CSV-faithful; `alpha_leaf`/`r_sto`
   translation stays in Phase 3.
5. **METHODOLOGY by reference** — pointer doc only; physics spec not copied into v1.

---

## Deviations from the plan

- Added `treeheat/io/schema.py` as shared validation module (plan implied shared spec; not a
  separate file but cleaner than duplicating validators).
- Full `validate_config()` still fails on `weather_file` and `grid_records_dir` (not placed in
  Phase 2; expected). Species + material paths resolve and pass.

---

## Test / acceptance status

```text
uv run pytest — 22 passed, 1 skipped (acceptance gate placeholder)
```

Phase 2 done criteria met:
- Loaders return validated, typed records
- Schema-conformance test guards both CSVs
- METHODOLOGY referenced as authoritative, not duplicated
- Config paths for species + material databases resolve to existing files

---

## Next step

**Phase 3** — physics behind the engine interface; wire `SpeciesRecord`/`MaterialRecord` into
integrator and port ground/surface/soil modules.
