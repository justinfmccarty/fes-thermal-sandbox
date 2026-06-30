# Housekeeping — Post Phase 6

**Date:** 20260630-0944
**Scope:** Repo cleanup after Phases 0–6 complete; conservative deletions only.

## What was cleaned

### Retired `proposed_skeleton/`

- Deleted 33 tracked stub files under `.agent/handoff/proposed_skeleton/` (NotImplementedError placeholders superseded by `treeheat/`).
- Replaced with a one-line pointer README linking to `../../treeheat/`.

### Updated orientation docs (skeleton → built v1)

- `.agent/handoff/README.md` — table + one-liner now point at `treeheat/`; Phases 7–8 remain.
- `.agent/handoff/01_project_description.md` §5 — handoff item 3 is the built pipeline.
- `.agent/handoff/02_codebase_guide.md` — layering note references `treeheat/`.
- `.agent/handoff/03_consolidation_recommendations.md` — companion line, Rec. 4/5 wording, sequencing section marked Phases 1–6 done.
- `.agent/handoff/04_archive_map.md` — top-level table adds `treeheat/` row; handoff row no longer lists skeleton as working tree.
- `.agent/handoff/05_workflow_interface.md` §8 — orchestration marked built; UI still Phase 8.
- `AGENTS.md` — repo holds v0 archives + v1 at `treeheat/`.
- `.cursor/rules/GENERAL.mdc` — agent rule updated to extend v1, not build from scratch.
- `treeheat/README.md` — reflects Phases 1–6 complete, acceptance PASS, CLI/orchestration quick start.

### `.gitignore` reconciliation

- Root `.gitignore` header notes v1; added explicit `treeheat/outputs/` rule (redundant with nested ignore, belt-and-braces).
- `treeheat/.gitignore` — added `.venv/`, `venv/`, `env/`, `*$py.class` for parity with root Python rules.
- Confirmed `treeheat/uv.lock` is **not** ignored (committable).
- Confirmed ignored: `__pycache__/`, `*.pyc`, `*.egg-info/`, `.pytest_cache/`, `.venv/`, `outputs/`.

### Local cruft removed (unambiguous, regenerable)

- All `__pycache__/` directories (repo-wide, excluding nothing committed).
- All `.pytest_cache/` directories.
- All `.DS_Store` files.
- All `*.pyc` and `*.egg-info/` if present.

### Memory index

- Verified `.agent/local_memory/INDEX.md` already has one entry per Phase 0–6.
- Phase 0–5 memory files exist on disk but were untracked before this session (not committed by this housekeeping pass).

## What was left (and why)

| Item | Reason |
|------|--------|
| `treeheat/.venv/` (~371 MB) | Local dev env; gitignored; regenerable via `uv sync` |
| `treeheat/outputs/` (~170 MB) | v1 run artifacts; gitignored; useful for inspection without re-run |
| Root `.venv/` | Gitignored local env |
| `src_archive/debug_run.log` | Tracked v0 reference; ambiguous — may document a historical run |
| `src_archive/debug_material_assignment.py`, `create_debug_grid_mapping.py` | Tracked v0 scaffolding; ambiguous — may hold validation logic worth mining for tests |
| Honeybee `__logs__/` under `model_archive/` and `src_archive/grasshopper/` | Tracked v0 run logs; ambiguous — part of model archive record |
| `.agent/local_memory/v1_build_prompts.md` (modified, unstaged) | Pre-existing edits; not part of housekeeping scope — review separately |
| `.agent/handoff/06_retired_scripts.md` (untracked) | Useful Phase 5 doc; left for separate commit batch with `treeheat/` |
| Entire `treeheat/` package (untracked) | Primary v1 deliverable; left uncommitted per plan ("no commits unless requested") |
| Phase 0–5 memory `.md` files (untracked) | Should be committed with next batch to fix INDEX links in a fresh clone |

## v0 archive status

- `src_archive/`, `model_archive/`, `analysis_archive/` — **no modifications** in this housekeeping pass (`git status` clean for those paths).
- Phase 6 deletions (`debug_raytracing_results/`, `debug_outputs/`, `archive/`, debug grid CSVs) remain as committed in `ea4eb49`.

## Verification

```
git check-ignore treeheat/uv.lock  → not ignored (committable)
git check-ignore treeheat/.venv    → ignored
git check-ignore treeheat/outputs/ → ignored
git status src_archive model_archive analysis_archive → no changes
cd treeheat && uv run pytest -q --ignore=tests/test_acceptance.py → 34 passed in 2.70s
```

Slow acceptance tests (3) not re-run in housekeeping; last PASS recorded in Phase 4 memory.

## Deviations from plan

- None. Did not commit changes (plan specified no commits unless separately requested).
- Did not modify `v1_build_prompts.md` — flagged for human review instead.

## Remaining repo work (out of scope)

- Commit `treeheat/` + `uv.lock` + phase 0–5 memory files + handoff updates.
- Phase 7 (Stage 2→3 spike) and Phase 8 (Streamlit UI).
