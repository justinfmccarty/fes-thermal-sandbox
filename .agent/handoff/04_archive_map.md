# Archive Map — Where to Look, Without Reading Everything

> **Purpose:** A token-cheap index for agents. Each entry says *what is here* and *when to open it*. Read this file first; open archive files only when an entry below tells you they answer your question.
> **Golden rule:** the archive is **reference, not the working tree**. Do not load whole directories. Use the "Look here when…" column to jump straight to the one file you need.
> **Sizes flagged** because some files are huge — don't open binaries or `*.feather`/`*.pkl` blindly.
> **Path convention:** every path in this file is **relative to the repository root** (`thermal-sandbox/`), e.g. `src_archive/radiance.py` means `thermal-sandbox/src_archive/radiance.py`. This is *not* relative to this document — the handoff itself lives at `.agent/handoff/`, two levels down. From this doc, an archive file is `../../src_archive/...`.

---

## Top level

| Path (from repo root) | What it is | Look here when… |
|------|------------|-----------------|
| `analysis_archive/conference_paper.pdf` | The published first-attempt paper (1.3 MB) | You need the scientific framing, results, or claims as written. |
| `model_archive/` | Stage 2 Rhino/Grasshopper artifacts (131 MB) | You need the 3D geometry, the GH definition, or sky-view-factor inputs. |
| `src_archive/` | Stages 3–5 code + data (1.4 GB) | Everything about the simulation pipeline. |
| `.agent/handoff/` | This handoff (orientation docs) | Orientation. Start here, not in the archives. |
| `treeheat/` | v1 working pipeline (Phases 1–6 complete) | The config-driven CLI, orchestration core, and acceptance-tested pipeline. |
| `.agent/local_memory/` | Agent working memory | Agent state; not project source. |

---

## `src_archive/` — orientation files (read these, they're small)

| File | Look here when… |
|------|-----------------|
| `METHODOLOGY.md` | **You need the physics.** Equations, constants, energy-balance diagram, references. Authoritative. |
| `config.yaml` | You need a parameter value or path. Single source of truth: paths, analysis period, constants, CEB params, species/soil/risk defaults, simulation settings. |
| `README.md` | You need the original two-phase workflow description and file-format examples. |
| `PLOT_FORMATTING_GUIDE.md` | You're reproducing the paper's figure style. |
| `REFACTOR_SUMMARY_MIDDLE_SCENARIO.md` | You need history on the "middle scenario" (50/50 reference) refactor. |
| `update_CEB_model.md` | You need the change history of the Li-2023 CEB integration. |

---

## `src_archive/` — code by question

**"How is X computed?"** → open exactly one module:

| Question | File |
|----------|------|
| Annual irradiance / Radiance / feather outputs | `radiance.py` |
| Reflected (upwelling) shortwave | `upwelling_calculator.py` |
| Ground temperature `Tg` | `ground_temperature.py` |
| Surface temp & MRT | `surface_energy_balance.py` |
| Leaf temperature — **current** engine | `li2023_ceb_model.py` |
| Leaf temperature — **legacy** engine | `leaf_energy_balance.py` |
| Soil moisture / stomatal coupling | `soil_moisture.py` |
| The thing that couples all of the above | `biophysical_tree_stress.py` (the integrator) |
| Heat-stress metrics (degree-hours, exceedance) | `risk_metrics.py` |
| Cross-scenario aggregation & ranking | `results_analysis.py` |
| Species parameters / loading | `tree_species.py` |
| Weather/EPW loading, warmest-week logic | `weather_loader.py` |
| Grid→material assignment per scenario | `grid_material_mapping.py` |
| Config access | `config_locator.py` |
| Plots | `plots.py`, `plot_formatting.py`, `visualization.py` |
| Misc helpers | `utils.py` |

**"How is the whole thing run?"**

| File | Note |
|------|------|
| `run_analysis.py` | **Canonical** analysis entry point. Config-driven. Start here. |
| `material_scenario_workflow.py` | The engine class (Phase 1 raytracing → Phase 2 analysis). Reusable core. |
| `04_run_workflow.ipynb` | Walks the full Phase 1–3 sequence interactively. |
| `05_paper_analysis.ipynb` | Loads results pickle, makes the paper's figures. |

**Do NOT treat as entry points** (hardcoded paths, historical): `workflow.py`, `workflow_analysis.py`, `example_usage.py`.

**Ignore unless debugging history** (one-off scaffolding): `debug_material_assignment.py`, `verify_hour_indexing.py`, `verify_material_changes.py`, `verify_scenario_materials.py`, `create_debug_grid_mapping.py`, `populate_scenario_materials.py`, `regenerate_raytracing.py`, `tree_species_database_mapping.py`, and the ad-hoc `test_*.py` scripts.

---

## `src_archive/` — data by question

| Need | Path | Notes |
|------|------|-------|
| Species physiology params | `tree_species_database.csv` | 34 rows, citation-backed columns. |
| Material thermal/optical props + naturalness | `root_material_database.csv` | 16 rows. |
| Weather | `weather.epw` | Winnipeg TMY. |
| Tree point locations | `grid_records/baseline_trees.csv` | xcoord,ycoord,zcoord,number (~147 trees). |
| Baseline sensor grid | `grid_records/jodla_baseline_grid.csv` | Dense. |
| Scenario sensor grid | `grid_records/jodla_scenario_grid.csv` | Sparse/fast (17,399 sensors). Matches the feather files. |
| Material assignments per scenario | `grid_records/scenario_grid_materials.csv` | + `..._template.csv` is blank. |
| Baseline material props | `grid_records/baseline_materials.csv` | ground vs facade tagged. |
| **Final example output report** | `analysis_outputs/analysis_report.md` | The headline numbers (25 scenarios, 147 trees, sensitivity slopes). Quick read. |

**Large generated outputs — don't open blindly:**

| Dir | Size | Contents |
|-----|------|----------|
| `raytracing_results/` | 500 MB | `*_direct.feather`, `*_diffuse.feather` per scenario. |
| `analysis_outputs/` | 274 MB | `biophysical_results_*.csv`, `baseline_trees.csv`, `analysis_report.md`. |
| `outputs/` | 163 MB | `biophysical_results_*.csv`, `*_scenario_analysis_results.pkl`. |
| `archive/` | 137 MB | older outputs + `dev_docs/` + `tree_species_database_old.csv`. |
| `debug_raytracing_results/` | 134 MB | **throwaway** debug feathers. |
| `debug_outputs/` | 5 MB | throwaway. |
| `plots/` | 14 MB | figures. |
| `grid_records/debug_*` | — | throwaway grid duplicates. |

> To inspect a feather/pkl, load a **single** file with pandas and `.head()` — never read a directory of them into context.

---

## `src_archive/python/` and `grasshopper/` — the Radiance projects

| Path | Look here when… |
|------|-----------------|
| `python/baseline_radiance_project/model/` | You need the **immutable** baseline Radiance scene (`scene/envelope.mat`, `envelope.rad`). Reference geometry/materials. |
| `python/scenario_radiance_project/model/` | Same structure, **optimized/sparser grids** for fast scenario runs. |
| `grasshopper/baseline_radiance_project/`, `grasshopper/scenario_radiance_project/`, `grasshopper/svf/` | The GH-side of the same projects + sky-view-factor work. |

---

## `model_archive/DLA Study Model/` — Stage 2 (Rhino/Grasshopper)

| File | Look here when… |
|------|-----------------|
| `build_radiance_model.gh` | You need to understand or re-run the **geometry→Radiance export** (the fragile Stage 2→3 seam). Requires Rhino + Grasshopper + plugins. |
| `Honeybee Smaller Study Model.3dm` | You need the actual 3D Rhino model. |
| `svf/DLA_Study.hbjson` | You need the Honeybee model (JSON) — geometry + metadata without Rhino. |
| `svf/sky_view_inputs.json`, `svf/sky_vectors.txt`, `svf/sky_view/` | You need sky-view-factor inputs/outputs. |

---

## Fast triage cheatsheet for an agent

- **"What's the science?"** → `src_archive/METHODOLOGY.md` (+ paper PDF).
- **"What were the results?"** → `src_archive/analysis_outputs/analysis_report.md`.
- **"How do I run it?"** → `src_archive/run_analysis.py` + `config.yaml`.
- **"Where's parameter X?"** → `src_archive/config.yaml`.
- **"How is quantity Y computed?"** → the single module in the table above.
- **"Where's the geometry?"** → `model_archive/.../*.3dm` or `svf/DLA_Study.hbjson`.
- **"Can I trust this script?"** → if it's in the "do not treat as entry points" / "ignore" lists, no.
- **"Is this file huge?"** → anything under `*_results/`, `outputs/`, `*.feather`, `*.pkl`. Sample one file, never the dir.
