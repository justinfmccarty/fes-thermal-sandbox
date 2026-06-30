# data/

Inputs the pipeline reads (ported from `src_archive/`):

- `weather.epw` — Winnipeg TMY *(Phase 2+ placement)*
- `tree_species_database.csv` — **33 species rows** (carry schema unchanged)
- `root_material_database.csv` — **15 material rows**
- `grid_records/` — sensor grids + scenario material assignments *(Phase 2+ placement)*

Physics spec: see [`../docs/methodology.md`](../docs/methodology.md) — points at the
authoritative `src_archive/METHODOLOGY.md`; do not duplicate it here.

## Material database notes

The columns `heat_capacity_J_m2_K`, `evap_factor`, and `k_drain` are present in the CSV
schema but intentionally blank. Ground thermal and evaporation properties resolve from
`config.model.ground.types[ground_type]` in `config/defaults.yaml`.

Large simulation **outputs** do not live here — they are generated into `outputs/`
and git-ignored. See the data-retention decision in
`.agent/handoff/03_consolidation_recommendations.md`.
