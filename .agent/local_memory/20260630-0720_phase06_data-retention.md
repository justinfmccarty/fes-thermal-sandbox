# Phase 06 — v0 Data Retention (Rec. 5)

**Date:** 2026-06-30 07:20
**Phase:** 6 (human-led data-retention decision; housekeeping + forward layout)
**Inputs read:** `.agent/handoff/03_consolidation_recommendations.md` Rec. 5, `.agent/handoff/04_archive_map.md`, Phase 0–5 memory, measured disk/git state, `treeheat/tests/test_acceptance.py`, `treeheat/treeheat/config.py`.

---

## Decision (human)

After reviewing Options 1 (commit canonical set), 2 (LFS/DVC), and 3 (regenerate-on-demand), plus a tiered hybrid, the human confirmed:

1. **This is the only machine that will ever use the v0 archive** — no distribution audience.
2. **Off-machine backup already exists** — manual restore to expected paths anytime; disk failure is not a project risk.
3. **No backwards development after v1** — v0 outputs are acceptance-gate fixtures only during the port (gate already PASS, Phase 4).
4. **Future users work on external projects** — project dirs live outside the repo; their outputs are never git-tracked.
5. **Both optional extras accepted:** (a) delete throwaway debug/archive dirs; (b) commit the ~16 KB headline CSVs for documentation.

**Effective policy:** status quo for heavy v0 data (gitignored on disk, preserved off-machine); optional housekeeping applied; forward layout principle codified below.

---

## What was done

1. **Deleted throwaway (~275 MB reclaimed):**
   - `src_archive/debug_raytracing_results/` (133 MB)
   - `src_archive/debug_outputs/` (5 MB)
   - `src_archive/grid_records/debug_*.csv` (3 files)
   - `src_archive/archive/` (137 MB, superseded outputs)

2. **`.gitignore` updated** ([`.gitignore`](../../.gitignore)):
   - Removed ignore rules for deleted debug/archive dirs (no longer exist).
   - Un-ignored `src_archive/analysis_outputs/sensitivity_analysis.csv` and `pct_change_summary.csv` alongside existing `analysis_report.md`.
   - Header comment updated to reflect Phase 6 decision (no LFS/DVC; off-machine backup; repo = code + small reference only).

3. **Committed to git (documentation anchor):**
   - `sensitivity_analysis.csv` (5.5 KB) — paper regression inputs
   - `pct_change_summary.csv` (8 KB) — per-scenario pct-change vs 50/50 ref

4. **Left unchanged (by design):**
   - `src_archive/raytracing_results/` (500 MB feathers) — gitignored, on disk, off-machine backup
   - `src_archive/analysis_outputs/biophysical_results_*.csv`, plots — gitignored, regenerable (~1 min via `treeheat run all`)
   - `src_archive/outputs/` (162 MB) — gitignored
   - `model_archive/` (130 MB geometry) — committed as source input
   - `treeheat/outputs/` — gitignored (v1 generated outputs)

---

## Key decisions recorded

| Topic | Decision |
|-------|----------|
| v0 heavy outputs | Keep gitignored on disk; preservation = off-machine backup + manual restore |
| git/LFS/DVC for v0 | **Rejected** — no clones, no shared remote, no distribution need |
| Headline anchor | Commit report + two CSVs (~16 KB) as diffable paper numbers in git history |
| Throwaway debug/archive | **Deleted** from working tree |
| Future projects | External project dirs; outputs never in this repo |
| Post-v1 validation | Test v1 against a new user's external project (new case, not v0 replay) |

---

## Forward data-layout principle

**Repo ships code + small reference data only.** All generated data — v0 archive outputs and every future project's outputs — stays untracked and lives on disk in project-specific locations.

v1 already supports external projects via [`treeheat/treeheat/config.py`](../../treeheat/treeheat/config.py):

- `get_config(path)` accepts an explicit config file location.
- Absolute paths in config resolve as-is; relative paths resolve against the **config-file directory**.
- An external project at e.g. `~/projects/site-X/config/config.yaml` runs via `treeheat run all --config …` and writes outputs under paths declared in that config — this repo's git never sees them.

**Caveat (flag for Phase 8 / UI):** `get_config` loads `defaults.yaml` from the same directory as the run config (`config_dir / "defaults.yaml"`). An external project's `config/` must contain **both** `defaults.yaml` and `config.yaml` (copy repo `treeheat/config/` as template). Eventually: `treeheat init <project-dir>` scaffold — not built in Phase 6.

---

## Deviations from the original Rec. 5 memo options

- Original Rec. 5 listed three engineering options (commit / LFS-DVC / regenerate). Human constraints (single machine, existing backup, no backwards dev, external future projects) **collapsed all three to "status quo + housekeeping."**
- Tiered hybrid recommendation (LFS for feathers) was **not adopted** — backup replaces VCS for preservation.
- No `REBUILD.md`, no `MANIFEST.sha256` — backup + manual restore deemed sufficient.

---

## Test / acceptance impact

**None.** Acceptance gate unchanged:

- Fast tier still reads v0 `biophysical_results_*.csv` + headline CSVs from `src_archive/analysis_outputs/` (on disk, gitignored except the three anchor files).
- Slow tier still reads v0 `raytracing_results/*.feather` (on disk, gitignored).
- Gate passed Phase 4; no re-run required for Phase 6.

---

## Next step

**Phase 7** — Stage 2→3 automation spike (Rhino/GH → Radiance export), or **Phase 8** — researcher-facing workflow UI (thin Streamlit skin), per roadmap.
