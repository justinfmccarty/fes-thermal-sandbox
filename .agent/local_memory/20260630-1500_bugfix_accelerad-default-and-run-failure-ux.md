# Bugfix/UX — Accelerad default + run-failure reporting in the UI

**Date:** 2026-06-30 15:00
**Scope:** follow-up to Phase 8 (surfaced running the kings-road capstone through the UI)

Two independent issues, both reported from a real run.

## 1. Accelerad required by default but installed by almost no one

**Symptom:** `Pipeline error: Accelerad command 'accelerad_rfluxmtx' not found in PATH.`

**Cause:** `treeheat/defaults.yaml` shipped `simulation.use_accelerad: true`, and
`radiance/runner.py` *hard-raised* `FileNotFoundError` in both `run_rfluxmtx` and
`run_rcontrib` when the Accelerad binaries were absent. Accelerad is a niche GPU build of
Radiance; standard users only have the standard tools bundled with pyradiance.

**Fix (`treeheat/treeheat/...`):**
- `defaults.yaml`: `use_accelerad: false` (standard Radiance is the default for everyone).
- `radiance/runner.py`: added `accelerad_available()` and `resolve_accelerad(flag)`.
  `resolve_accelerad` honors the request only if *both* Accelerad commands resolve on
  PATH; otherwise it prints a one-line warning and returns `False`. Called once at the top
  of `run_2phase_dds` (single warning per run) and defensively at the top of
  `run_rfluxmtx`/`run_rcontrib` (robust when called standalone). The old hard `raise`
  guards were removed — a missing Accelerad now falls back instead of aborting. Even a
  project whose `config.yaml` explicitly sets `use_accelerad: true` will run.
- Setup UI (`app/screens/setup.py`): added a "Use Accelerad (GPU ray tracing)" checkbox
  that persists `simulation.use_accelerad` into `config.yaml`, with help text noting the
  automatic fallback. (Earlier user note: the UI should be able to control these.)

## 2. Failed run kept polling with no clear report

**Symptom:** when a run failed, the Run screen kept auto-refreshing every 5 s and never
made the failure obvious.

**Cause:** `app/screens/run_screen.py` always slept 5 s and `st.rerun()`'d regardless of
state. The runner *does* write `status: failed` into `run_state.json` (with full
traceback in `error`), but the UI never read the lifecycle or stopped. It also could not
detect a hard crash (process dies leaving a task stuck at `running`).

**Fix (`app/screens/run_screen.py`):**
- Added `_run_phase(state, pid_running)` → `running | failed | crashed | complete | idle`.
  - `failed`: any task `status == failed`.
  - `crashed`: a task still `running` but the launched PID is no longer alive.
  - `running`: PID alive (or just launched, no tasks yet).
  - `complete`: PID gone, tasks exist, none failed/running.
  - `idle`: no tasks, PID gone.
- Auto-refresh now fires **only** while `phase == "running"`. Failure/crash/complete/idle
  stop polling so the report stays on screen. Added an always-available "Refresh now"
  button for manual polling.
- On `failed`/`crashed`: a red banner, the per-task full traceback in an expanded
  `Error — <task>` panel, and the run-log tail expanded (80 lines). On `complete`: green
  success banner. The task table now shows only the first line of each error (full text
  lives in the expander).

## Verification

- New helpers unit-checked inline: `accelerad_available()` False on this machine;
  `resolve_accelerad(True)` → False with warning; `_run_phase` returns
  idle/running/crashed/failed/complete for the matching state+pid combinations.
- Confirmed kings-road `config.yaml` has no `use_accelerad` override → now inherits the
  `false` default.
- Full suite incl. capstone end-to-end (real Radiance run via the fallback): **47 passed**.

## Follow-up regression fix (same session)

`_task_summary` crashed with `IndexError: list index out of range` on the first render:
the new one-line error preview used `(rec.get("error") or "").splitlines()[0]`, but
`"".splitlines()` is `[]`, so any task without an error (every `done`/`running`/`pending`
task) blew up. Guarded it: `error_lines[0][:120] if error_lines else ""`. Verified against
empty-string, `None`, and multiline errors.

## Notes / deviations

- Chose *both* flip-default and runtime-fallback (not just one): the default keeps new
  projects correct, the fallback keeps any pre-existing `use_accelerad: true` config from
  crashing. No contract/layout changes.
- `crashed` detection is a heuristic (stale `running` + dead PID); PID reuse on this
  timescale is treated as acceptable risk.
