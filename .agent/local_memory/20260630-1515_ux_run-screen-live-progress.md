# UX — Run screen live progress + log buffering fix

**Date:** 2026-06-30 15:15
**Scope:** follow-up to Phase 8 (user feedback: Radiance visibly running in Activity
Monitor, but the Streamlit log tail showed no progress; polling/naming unclear)

## Root causes

1. **Log appeared frozen.** `app/background.py` launched `treeheat run` with the child's
   stdout redirected to a *file*. Python block-buffers stdout when it is not a TTY, so the
   runner's `print()` progress lines sat in an 8 KB buffer instead of reaching `run.log`
   live. Compounding it: the heavy Radiance calls (`rfluxmtx`, `rcontrib`) legitimately
   emit no output for minutes, so even unbuffered there are long silent stretches that
   look like a freeze.
2. **Confusing tail.** The log was opened in append mode, so every launch stacked on top
   of stale prior runs in the same file.
3. **Unclear UX.** "Run state" + a raw `stage:scenario` table + a whole-page
   `time.sleep(5); st.rerun()` loop gave no sense of *what* was happening or *how long*.

## Changes

`app/background.py`
- Launch with `python -u` **and** `PYTHONUNBUFFERED=1` in the child env → runner prints
  stream to `run.log` immediately.
- Open `run.log` in write mode (truncate) so the log reflects only the current run.

`app/screens/run_screen.py` (rewrote, guided by the version-matched Streamlit 1.58 skill)
- **Live updates via `st.fragment(run_every="3s")`** instead of a full-page sleep/rerun.
  Only the progress panel reruns while active. Top level decides: if phase is `running`,
  mount the fragment; otherwise render a static report (no polling). When the fragment
  detects the run left `running`, it fires one full `st.rerun()` to drop to the static
  report — clean stop, no infinite loop.
- **Status header with badges** (`st.badge`, Material Symbols): Running / Complete /
  Failed / Stopped / Ready, each with a one-line caption.
- **Liveness signals while running:** parsed "Now: <last log line>" current step, an
  **elapsed** timer (from the running task's `started_at`), and an explicit note that
  Radiance steps can run minutes with no new lines (so silence ≠ freeze).
- **Friendly task view:** stage labels (`raytrace`→"Ray tracing", etc.), Scenario, Status,
  and computed Duration; KPI row of bordered `st.metric` (Done / Running / Failed).
- **Failure report:** per-failed-task expander (expanded) with full traceback; the live
  log is always shown in a bordered "Live output" card.
- Cleaner launch card: `st.segmented_control` for stage, `st.toggle` for force, primary
  Launch button with a play icon and a `st.toast` confirmation; active-run dot indicator.

## Verification

- Streamlit 1.58 confirmed to expose every API used (badge, segmented_control, toggle,
  metric(border), container(horizontal), fragment(run_every), width="stretch", toast).
- Module imports clean; pure helpers unit-checked (`_run_phase`, `_fmt_duration`,
  `_current_activity`, `_task_rows`).
- Fast suite: 41 passed (UI is not covered by tests). App live on :8501 (hot-reload).

## Follow-up — structured progress tracker (user: "live output is still useless")

A raw log dump is unhelpful because the heavy Radiance steps emit nothing for minutes.
Replaced it with a parsed **DDS progress tracker** (`_dds_progress`, `_render_dds_tracker`
in `run_screen.py`):
- Focuses on the current scenario's log segment (splits on the last
  `"Running 2-Phase DDS"` marker).
- Renders the four macro phases — Weather prep, Part 1 (total), Part 2 (direct),
  Part 3 (sun) — each with a done/running/pending colored Material icon, plus the
  currently-running Radiance sub-step (`oconv`/`rfluxmtx`/`rcontrib`/`gendaymtx`/
  `dctimestep | rmtxop`) detected via the runner's "started"/"completed in" markers.
- Two `st.progress` bars: scenarios complete (N/total from run-state) and current-scenario
  phases complete (k/4). Elapsed moved into the "Running" badge label.
- Raw log demoted to a collapsed "Full log" expander (auto-expands on failure).
- Parser unit-verified across mid-run, phase-transition, and finished snapshots.

Confirmed there is no native Radiance progress stream worth wiring: `rcontrib`/`rfluxmtx`
do not emit usable progress to stdout/stderr (no `-t`-style reporting like `rpict`), so
parsing the runner's own phase prints is the right source of truth.

## Follow-up — Stop button + zombie-reap fix

Added a **Stop run** control (shown in the running status panel).
- `app/background.py::stop_background_run` signals the run's *process group*
  (`os.killpg(os.getpgid(pid), SIGTERM)`, escalating to SIGKILL after a 5 s wait). Because
  the run is launched with `start_new_session=True`, the group includes the Python runner
  *and* its spawned Radiance subprocesses, so they all go down together. Falls back to a
  single-pid signal if the group lookup fails.
- Run-screen: red secondary "Stop run" button → `stop_background_run(root)` + toast +
  `st.rerun()`. After stopping, the dead-PID + still-`running` task resolves to the
  `crashed`/"Stopped" phase, which already stops polling and shows the log.

**Important latent bug fixed while testing Stop:** the run subprocess is a child of the
Streamlit process, so when it exits it becomes a *zombie* until reaped; `os.kill(pid, 0)`
reports a zombie as alive, which would have pinned `is_process_running` (and thus the run
phase) on "running" forever — including after a *normal* completion. `is_process_running`
now reaps via `os.waitpid(pid, WNOHANG)` first and treats a reaped pid as not running.
Verified end-to-end: Stop kills the whole group; a finished child is reported not-running.

## Notes / deviations

- Did not attempt to stream Radiance's own per-ray progress (the tools don't emit usable
  progress); the phase tracker + elapsed + progress bars communicate liveness instead.
- A manual stop surfaces as the "Stopped" (crashed) phase rather than a distinct
  user-cancelled state — acceptable; the badge reads "Stopped" and polling halts.
