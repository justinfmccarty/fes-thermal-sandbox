# Runbook: Grasshopper → treeheat-ready project

Manual procedure for exporting a Rhino/Grasshopper (Honeybee/Ladybug) model into
an **external treeheat project directory**. No automation — follow these steps
reliably each time you onboard a new site.

## Prerequisites

- Rhino 7+ with **Honeybee** and **Ladybug** (or compatible) plugins
- Radiance installed and on `PATH` (for later raytracing runs)
- `treeheat` installed (`uv sync` in the `treeheat/` package directory)

## Overview

```
Rhino/GH model  →  Radiance projects + CSV grids  →  treeheat init  →  populate  →  validate  →  run
     Stage 2              Stage 2→3 seam                  external project dir
```

## Step 1 — Scaffold the project directory

Choose a location **outside** the treeheat git repo (e.g. `~/Projects/my_site/`):

```bash
treeheat init ~/Projects/my_site
```

This creates `config/config.yaml`, `runbook_gh_to_project.md`, `models/` (for your
`.3dm` / `.gh` files), `inputs/`, `outputs/` (git-ignored), starter species/material
databases, and placeholder files for everything the runbook fills in.

## Step 1b — Store source models (optional)

Copy your Rhino and Grasshopper files into `models/` for reference. The pipeline
does not read this folder — exports still go into `inputs/` per the steps below.

## Step 2 — Export weather

1. In Ladybug, select or download a TMY EPW for your site.
2. Save/copy it to:

   `inputs/weather.epw`

## Step 3 — Export tree points

From your GH definition (see reference: `model_archive/DLA Study Model/build_radiance_model.gh`):

1. Export individual tree locations as a CSV with columns:
   - `tree_id` (or `number`), `xcoord`, `ycoord`, `zcoord`, `species` (optional), `SVF` (optional)
2. Save to:

   `inputs/grid_records/baseline_trees.csv`

## Step 4 — Export sensor grids

Grasshopper typically exports two grids. Save both:

1. **Scenario sensor grid** (the one the pipeline uses) — must match the per-scenario
   raytrace feather columns exactly:

   `inputs/grid_records/scenario_sensor_grid.csv`

2. **Baseline sensor grid** (optional reference; for the annual baseline run):

   `inputs/grid_records/baseline_sensor_grid.csv`

Columns for both: `grid_name`, `xcoord`, `ycoord`, `zcoord` (names may vary; treeheat normalizes common aliases).

> **Critical:** `scenario_sensor_grid.csv` drives biophysics. Its sensor count and order
> must match the Radiance feather output columns exactly, or biophysics fails with a
> clear sensor-count error. The baseline grid is reference-only and not read by the
> per-scenario pipeline.

## Step 5 — Export the baseline material mapping

1. **Baseline materials** — grid cell → material name, tagged ground vs facade:

   `inputs/grid_records/baseline_materials.csv`

   Columns: `grid_id`, `material_name`, `ground_or_facade` (optional: `area_m2`)

2. **Scenario materials are generated, not exported.** `treeheat` derives
   `inputs/grid_records/scenario_grid_materials.csv` from the baseline mapping
   above plus the scenario instructions in `config/config.yaml`, using the same
   naturalness logic as the ray tracer. It is created automatically the first
   time biophysics runs; to (re)generate it explicitly:

       uv run treeheat materials --config config/config.yaml

Customize `inputs/root_material_database.csv` if your site uses materials not in the starter set.

Ensure `inputs/base_material_library.txt` contains Radiance `void plastic …` definitions for each material name referenced.

## Step 6 — Export Radiance projects

Export **two** Radiance project folders from Honeybee (baseline + scenario-optimized grid):

| Export | Target path |
|--------|-------------|
| Baseline (full annual, dense reference) | `inputs/radiance/baseline_radiance_project/` |
| Scenario (warmest-week grid, sparser) | `inputs/radiance/scenario_radiance_project/` |

Each project must contain:

```
model/
  scene/
    envelope.rad    # geometry with surface IDs (ground/facade keywords in names)
    envelope.mat    # material assignments
  grid/
    *.pts           # sensor point files
```

Surface IDs in `envelope.rad` should include keywords the pipeline recognizes:
`ground`, `terrain`, `pavement`, `landscape`, `grass` (landscape) and
`wall`, `facade`, `building` (facade).

### Reference layout (v0 DLA study)

See `src_archive/python/baseline_radiance_project/model/` for a working example.

## Step 7 — Validate

```bash
cd ~/Projects/my_site
treeheat validate --config config/config.yaml
```

Fix any `[✗]` items before running. `run_state.json` may show `[~]` until the first run — that is normal.

## Step 8 — Run the pipeline

CLI:

```bash
treeheat run all --config config/config.yaml
treeheat status --config config/config.yaml
```

UI (from the treeheat package directory):

```bash
uv sync --extra ui --extra viz --extra dev
uv run streamlit run app/streamlit_app.py
```

Open Setup → point at your project dir → Run → Results.

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Sensor count mismatch | `scenario_sensor_grid.csv` does not match raytrace feather columns |
| Missing envelope.rad | Radiance export incomplete; re-export from Honeybee |
| validate fails on weather | EPW path wrong or file is still the init placeholder |
| Raytrace hours | Normal for annual runs; UI launches background process — check `outputs/run.log` |

## Checklist (copy for each new site)

- [ ] `treeheat init <dir>` executed
- [ ] `models/` — Rhino `.3dm` and Grasshopper `.gh` stored (optional reference)
- [ ] `inputs/weather.epw` — real EPW
- [ ] `inputs/grid_records/baseline_trees.csv`
- [ ] `inputs/grid_records/scenario_sensor_grid.csv` (drives biophysics)
- [ ] `inputs/grid_records/baseline_sensor_grid.csv` (optional reference)
- [ ] `inputs/grid_records/baseline_materials.csv`
- [ ] `inputs/grid_records/scenario_grid_materials.csv` (auto-generated; `treeheat materials`)
- [ ] `inputs/radiance/baseline_radiance_project/model/scene/envelope.{rad,mat}`
- [ ] `inputs/radiance/scenario_radiance_project/model/scene/envelope.{rad,mat}`
- [ ] `treeheat validate` passes
- [ ] First run completes; `outputs/run_state.json` shows tasks `done`
