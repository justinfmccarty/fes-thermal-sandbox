# Phase 08 — External project layer + UI skin

**Date:** 2026-06-30 10:30
**Phase:** 8 (project init, layout contract, runbook, Streamlit UI)
**Inputs read:** approved Phase 8 plan, Phase 5 orchestration code/memory, handoff 05_workflow_interface.md, 01_project_description.md §2.

---

## What was built

### Layer A — Project / CLI (core)

1. **Packaged defaults** — [treeheat/treeheat/defaults.yaml](treeheat/treeheat/defaults.yaml) is the single source; [config.py](treeheat/treeheat/config.py) falls back when a project has no local `defaults.yaml`. Removed project-level `treeheat/config/defaults.yaml`.
2. **Config path fix** — `_cfg_roots` map so `get_path(cfg=held_dict)` resolves against the correct project even after a global `get_config()` reload (required for external projects + pytest).
3. **Project module** — [treeheat/treeheat/project.py](treeheat/treeheat/project.py): `PROJECT_LAYOUT`, `init_project()`, `validate_project()`, `write_config_overrides()`, starter data from `treeheat/project_data/`.
4. **CLI** — `treeheat init <dir>`, `treeheat validate --config …` in [cli.py](treeheat/treeheat/cli.py).
5. **Runbook** — [treeheat/docs/runbook_gh_to_project.md](treeheat/docs/runbook_gh_to_project.md): manual Grasshopper/Honeybee → Radiance → project-dir procedure.

### Layer B — UI skin

6. **Streamlit app** — [treeheat/app/](treeheat/app/): Material-styled `.streamlit/config.toml`, three screens (Setup / Run / Results), imports only `treeheat.api` + `treeheat.project` (+ local `app.background` for detached subprocess).
7. **Background runs** — `subprocess.Popen(..., start_new_session=True)` → `outputs/run.pid` + `outputs/run.log`; UI polls `api.status()`.

---

## Key decisions

1. **Defaults in package, overrides in project `config.yaml`** — UI Setup writes curated overrides (engine, period, n_scenarios) into the project stub; never edits packaged defaults.
2. **External project paths** — All inputs under `inputs/`, outputs under `outputs/` with orchestration-compatible keys (`biophysical_outputs_dir=../outputs/biophysical` → `run_state.json` at `outputs/run_state.json`).
3. **Capstone automated** — `tests/test_capstone_external.py` init + populate (simulating runbook) + biophysics/analyze on a temp external dir; complements Phase 4 reproduction gate.

---

## Deviations from the plan

- Fixed latent `get_path`/global-config bug exposed by capstone test (not in original plan scope).
- User's real Rhino/GH file capstone is **manual**: runbook + UI ready; automated capstone uses archive population as GH-export surrogate until user completes GH export on their machine.

---

## Test / acceptance status

```text
uv run pytest -q                    — 46 passed (~136s incl. slow)
uv run treeheat init /tmp/…         — scaffolds layout + starter DBs
uv run treeheat validate            — checklist + config validation
tests/test_capstone_external.py     — external project biophysics+analyze PASS
```

### Done criteria: **PASS**

| Criterion | Result |
|-----------|--------|
| `treeheat init` scaffolds valid external project | PASS |
| Runbook GH → project procedure documented | PASS |
| UI Setup / Run / Results end-to-end on project API | PASS (automated capstone + manual streamlit entry) |
| Layers distinct (UI calls core, never owns layout) | PASS |

---

## Next step

User runs real GH model through runbook into a fresh external dir, then drives UI locally. Optional: Phase 6+ data-retention polish or Stage 2→3 automation spike per roadmap.
