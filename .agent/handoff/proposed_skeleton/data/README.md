# data/

Inputs the pipeline reads (ported from `src_archive/`):

- `weather.epw` — Winnipeg TMY
- `tree_species_database.csv` — 34 species rows (carry schema unchanged)
- `root_material_database.csv` — 16 material rows
- `grid_records/` — sensor grids + scenario material assignments

Large simulation OUTPUTS do not live here — they are generated into `outputs/`
and git-ignored. See the data-retention decision in `../../03_consolidation_recommendations.md`.
