# Existing Codebase Guide — `src_archive/`

> **Purpose:** Explain what the existing v0 code *is*, what to trust, and what to ignore — so an agent building v1 can navigate it without reading every file.
> **Scope:** `src_archive/` (Stages 3–5 of the pipeline). For Stage 2 model artifacts see [`04_archive_map.md`](04_archive_map.md).
> **Rule of thumb:** the **modules** are good and reusable; the **orchestration scripts** are messy and should be read for intent, not copied.

---

## 1. The one thing to read first

If you read nothing else in the archive, read **[`src_archive/METHODOLOGY.md`](../../src_archive/METHODOLOGY.md)** and **[`src_archive/config.yaml`](../../src_archive/config.yaml)**.

- `METHODOLOGY.md` is the authoritative physics: every equation, constant, and reference, plus an energy-balance flow diagram.
- `config.yaml` declares itself the **single source of truth**. All parameters live there; code reads them through `config_locator.get_config()`. No hardcoded model defaults are *supposed* to exist (the orchestration scripts violate this — see §5).

---

## 2. The canonical run path (what to actually run)

There are five scripts that look like entry points. **Only one is the clean, config-driven path. Use this:**

```
config.yaml  ──►  config_locator.get_config()
                        │
   Phase 1 (raytracing) │   material_scenario_workflow.MaterialScenarioWorkflow
                        │   → runs Radiance per scenario → raytracing_results/*.feather
                        ▼
   Phase 2 (analysis)   │   run_analysis.py   ◄── THE canonical analysis entry point
                        │   → biophysics + risk + plots + analysis_report.md
                        ▼
                   analysis_outputs/
```

- **`run_analysis.py`** — *the* trustworthy entry point. Fully driven by `config.yaml` via `config_locator`. Produces the normalized percent-change analysis, sensitivity analysis, plots, and `analysis_report.md`. **Start here.**
- **`material_scenario_workflow.py`** — the real engine class (`MaterialScenarioWorkflow`). Orchestrates Phase 1 raytracing (temp working copies per scenario, feather output, cleanup) and can chain into biophysics. Sound design; this is the reusable core orchestrator.

The other three are **historical / notebook-style and should NOT be treated as entry points** — see §5.

---

## 3. Core modules (trust these — they are the reusable science)

Each has a real module docstring and reads parameters from `config.yaml`. Grouped by pipeline role:

### Configuration
| Module | Role |
|--------|------|
| `config_locator.py` | The **only** sanctioned way to read config. `get_config()`, `get_path()`. Enforces "no hardcoded defaults." |

### Inputs / IO
| Module | Role |
|--------|------|
| `weather_loader.py` | Loads EPW; extracts Ta, RH, wind, pressure; `find_warmest_day()`, `get_week_around_day()`. |
| `tree_species.py` | `TreeSpeciesDatabase` — species physiology (optical, stomatal, thermal thresholds) from CSV. |
| `grid_material_mapping.py` | Maps grid IDs (00…71) → material assignments per scenario. |
| `tree_species_database_mapping.py` | Maps observed trees → species-DB rows. (Borderline utility — see §5.) |

### Radiance (Stage 3)
| Module | Role |
|--------|------|
| `radiance.py` | 2-phase daylight-coefficient (DDS) annual irradiance via `pyradiance`. Outputs per-sensor direct + diffuse feather files. |
| `upwelling_calculator.py` | Reflected (upwelling) shortwave from downwelling + material albedo, via grid-material mapping. |

### Biophysics (Stage 4)
| Module | Role |
|--------|------|
| `biophysical_tree_stress.py` | `BiophysicalTreeStressCalculator` — **the integrator**; couples all physics modules per tree per hour. |
| `li2023_ceb_model.py` | **Current** canopy energy balance (Li et al. 2023). `config: ceb.enabled = true`. |
| `leaf_energy_balance.py` | **Legacy** leaf-temperature solver. Superseded by CEB. Kept for comparison only. |
| `ground_temperature.py` | 1-layer surface energy balance → ground temp `Tg` (responds to α, ε). |
| `surface_energy_balance.py` | Surface temperature + Mean Radiant Temperature (MRT). |
| `soil_moisture.py` | 1-layer bucket model; `SoilMoistureBucket` couples moisture → stomatal resistance. |

### Risk & analysis (Stage 5)
| Module | Role |
|--------|------|
| `risk_metrics.py` | Heat-stress metrics from leaf temperature (degree-hours, threshold exceedance). `calculate_stress_summary()`. |
| `results_analysis.py` | Aggregates risk across scenarios; statistical comparison; material-impact ranking. |

### Visualization
| Module | Role |
|--------|------|
| `plots.py` | Figure generation. |
| `plot_formatting.py` | Shared style/format. See `PLOT_FORMATTING_GUIDE.md`. |
| `visualization.py` | Additional/older plotting helpers (overlaps with `plots.py`). |
| `utils.py` | Misc helpers (`save_results`, `validate_inputs`, feather reconstruction). |

---

## 4. Data the code consumes and produces

### Inputs
- **`tree_species_database.csv`** — 34 species rows. Columns: light extinction k, leaf SW albedo, leaf emissivity, max stomatal conductance, VPD sensitivity (g1), optimal & critical leaf temp, leaf area/char size, plus per-cell citations.
- **`root_material_database.csv`** — 16 material rows. Columns: facade/ground applicability, naturalness score (0–1) + rationale, SW albedo, thermal emissivity, ground type, heat capacity, evap factor, drainage.
- **`weather.epw`** — Winnipeg TMY.
- **`grid_records/`** — sensor grids and material assignments (see §6).

### Outputs (large — see [`03`](03_consolidation_recommendations.md) on retention)
- **`raytracing_results/`** (~500 MB) — per-scenario `*_direct.feather` / `*_diffuse.feather`.
- **`outputs/`** (~163 MB) — `biophysical_results_*.csv`, scenario results `.pkl`.
- **`analysis_outputs/`** (~274 MB) — `analysis_report.md` + per-scenario biophysical CSVs + trees.
- **`plots/`** (~14 MB) — figures.

---

## 5. Accretion — read for intent, do not reuse

These are the byproducts of research-in-progress. They explain *how* things were debugged but are **not** part of a clean pipeline.

**Competing/legacy entry points (hardcoded paths, inline flags):**
- `workflow.py` — notebook-dump script; `sys.platform` branching; hardcoded `/Users/jmccarty/...`.
- `workflow_analysis.py` — hardcoded `Nextcloud/.../35_UHI_Trees_Manitoba`; builds the 25 scenarios inline; contains revealing comments (e.g. a removed `random.seed(42)` that had collapsed all scenarios to the same surfaces).
- `example_usage.py` — illustrative, hardcoded absolute paths.

**One-off scaffolding (`debug_*`, `verify_*`, `regenerate_*`, `populate_*`, `create_*`):**
`debug_material_assignment.py`, `verify_hour_indexing.py`, `verify_material_changes.py`, `verify_scenario_materials.py`, `create_debug_grid_mapping.py`, `populate_scenario_materials.py`, `regenerate_raytracing.py`. Each fixed a specific historical bug. Useful as a record of pitfalls; not pipeline code.

**Ad-hoc tests (not a real suite):**
`test_setup.py`, `test_li2023_ceb.py`, `test_material_application.py`, `test_scenario_period.py`. Validation scripts, not `pytest`-style regression tests.

**Notebooks:**
- `04_run_workflow.ipynb` — drives the workflow end-to-end (Phases 1–3); good for understanding the intended sequence.
- `05_paper_analysis.ipynb` — loads the results pickle and generates the paper's figures.

**Loose markdown (project memory, not spec):**
`REFACTOR_SUMMARY_MIDDLE_SCENARIO.md`, `update_CEB_model.md`, `PLOT_FORMATTING_GUIDE.md` — context on past changes; keep as history.

---

## 6. `grid_records/` — note the duplication

```
baseline_materials.csv             material props per baseline grid
baseline_trees.csv                 tree points (xcoord,ycoord,zcoord,number)
jodla_baseline_grid.csv            baseline sensor grid
jodla_scenario_grid.csv            scenario sensor grid (sparser/faster — 17,399 sensors)
scenario_grid_materials.csv        scenario material assignments
scenario_grid_materials_template.csv   blank template
debug_jodla_baseline_grid.csv      ⟵ debug duplicate
debug_jodla_scenario_grid.csv      ⟵ debug duplicate
debug_scenario_grid_materials.csv  ⟵ debug duplicate
```
The `debug_*` triplet are throwaway copies. Baseline vs. scenario grids differ deliberately: scenario grids are **sparser** to speed simulation. A known historical bug was a sensor-count mismatch between the grid file and the feather files (fixed by switching to `jodla_scenario_grid.csv`, 17,399 sensors).

---

## 7. Dependency sketch

```
config.yaml ─► config_locator ─► (everything)

run_analysis.py
   ├─ weather_loader
   ├─ tree_species ─ (tree_species_database.csv)
   ├─ grid_material_mapping ─ (grid_records/, root_material_database.csv)
   ├─ biophysical_tree_stress  ◄── integrator
   │     ├─ li2023_ceb_model        (current engine)
   │     ├─ leaf_energy_balance     (legacy engine)
   │     ├─ ground_temperature
   │     ├─ surface_energy_balance
   │     ├─ soil_moisture
   │     └─ upwelling_calculator ─ radiance (feather inputs)
   ├─ risk_metrics
   ├─ results_analysis
   └─ plots / plot_formatting
```

The dependency graph is clean and layered. **That is the asset worth preserving** when porting into the new skeleton — see [`03_consolidation_recommendations.md`](03_consolidation_recommendations.md).
