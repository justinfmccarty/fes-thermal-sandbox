"""Run screen — launch a background run and watch live progress.

Design notes:
- The pipeline runs as a detached subprocess; this screen never blocks on it.
- While a run is active, a single ``st.fragment`` polls run-state + the log every
  few seconds so only that panel reruns (no full-page refresh loop).
- When the run leaves the *running* state (done / failed / crashed) the fragment
  triggers one full rerun, which drops back to a static report and stops polling.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from treeheat import api
from treeheat.project import project_config_path

from app.background import (
    is_process_running,
    launch_background_run,
    read_run_log,
    run_pid_path,
    stop_background_run,
)

_STAGE_LABELS = {
    "all": "All stages",
    "raytrace": "Ray tracing",
    "biophysics": "Biophysics",
    "analyze": "Analysis",
}
_STAGE_CHOICES = {v: k for k, v in _STAGE_LABELS.items()}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _safe_status(cfg_path: Path) -> dict:
    try:
        return api.status(cfg_path)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not read run state: {exc}")
        return {}


def _pid_running(root: Path) -> bool:
    pid_path = run_pid_path(root)
    if not pid_path.exists():
        return False
    try:
        return is_process_running(int(pid_path.read_text(encoding="utf-8").strip()))
    except ValueError:
        return False


def _run_phase(state: dict, pid_running: bool) -> str:
    """``running`` | ``failed`` | ``crashed`` | ``complete`` | ``idle``."""
    statuses = [rec.get("status") for rec in state.get("tasks", {}).values()]
    if any(s == "failed" for s in statuses):
        return "failed"
    if any(s == "running" for s in statuses) and not pid_running:
        return "crashed"
    if pid_running:
        return "running"
    if statuses:
        return "complete"
    return "idle"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {sec}s"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def _task_rows(state: dict) -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    rows = []
    for key, rec in sorted(state.get("tasks", {}).items()):
        stage, _, scenario = key.partition(":")
        started = _parse_dt(rec.get("started_at"))
        finished = _parse_dt(rec.get("finished_at"))
        if started and finished:
            duration = _fmt_duration((finished - started).total_seconds())
        elif started and rec.get("status") == "running":
            duration = _fmt_duration((now - started).total_seconds())
        else:
            duration = ""
        rows.append(
            {
                "Stage": _STAGE_LABELS.get(stage, stage),
                "Scenario": scenario,
                "Status": rec.get("status", "pending"),
                "Duration": duration,
            }
        )
    return pd.DataFrame(rows)


def _running_elapsed(state: dict) -> str | None:
    now = datetime.now(timezone.utc)
    starts = [
        _parse_dt(rec.get("started_at"))
        for rec in state.get("tasks", {}).values()
        if rec.get("status") == "running"
    ]
    starts = [s for s in starts if s]
    if not starts:
        return None
    return _fmt_duration((now - min(starts)).total_seconds())


# Macro phases of a 2-phase DDS run, each with the log markers the runner prints
# at start and completion. Order matters — this is the progress sequence.
_DDS_PHASES = [
    ("Weather prep", "Initializing the weather file", "Weather file initialized"),
    ("Part 1 · total sky", "Starting Part 1", "Part 1 completed"),
    ("Part 2 · direct sky", "Starting Part 2", "Part 2 completed"),
    ("Part 3 · sun", "Starting Part 3", "Part 3 completed"),
]
# Radiance sub-steps printed within a phase as "     - <name>" then
# "         - <name> completed in N seconds".
_DDS_SUBSTEPS = [
    "create_sun_discs",
    "oconv",
    "rfluxmtx",
    "rcontrib",
    "gendaymtx",
    "dctimestep | rmtxop",
]


def _dds_progress(log_text: str) -> tuple[list[tuple[str, str]], str | None, bool]:
    """Parse the current scenario's DDS log segment.

    Returns ``(phases, current_substep, finished)`` where ``phases`` is a list of
    ``(label, state)`` with state in ``done|running|pending``.
    """
    segment = log_text
    marker = "Running 2-Phase DDS"
    if marker in log_text:
        segment = log_text[log_text.rfind(marker):]

    finished = "Simulation completed" in segment

    phases: list[tuple[str, str]] = []
    for label, start, done in _DDS_PHASES:
        if finished or done in segment:
            phases.append((label, "done"))
        elif start in segment:
            phases.append((label, "running"))
        else:
            phases.append((label, "pending"))

    current_sub: str | None = None
    for line in segment.splitlines():
        token = line.strip().lstrip("-").strip()
        for sub in _DDS_SUBSTEPS:
            if token == sub:
                current_sub = sub
            elif token.startswith(sub) and "completed" in token and current_sub == sub:
                current_sub = None
    if finished:
        current_sub = None
    return phases, current_sub, finished


def _raytrace_counts(state: dict) -> tuple[int, int]:
    """(#done, #total) raytrace scenarios."""
    rt = [
        rec
        for key, rec in state.get("tasks", {}).items()
        if key.startswith("raytrace:")
    ]
    done = sum(1 for r in rt if r.get("status") == "done")
    return done, len(rt)


def _active_task(state: dict) -> tuple[str, str] | None:
    """(stage, scenario) of the currently running task, if any."""
    for key, rec in sorted(state.get("tasks", {}).items()):
        if rec.get("status") == "running":
            stage, _, scenario = key.partition(":")
            return stage, scenario
    return None


_PHASE_STYLE = {
    "done": (":material/check_circle:", "green"),
    "running": (":material/sync:", "blue"),
    "pending": (":material/radio_button_unchecked:", "gray"),
}


def _render_dds_tracker(state: dict, log_text: str) -> None:
    active = _active_task(state)
    if active is None or active[0] != "raytrace":
        return
    _, scenario = active
    done_n, total_n = _raytrace_counts(state)

    phases, current_sub, finished = _dds_progress(log_text)

    headline = f"Ray tracing · **{scenario}**"
    if total_n > 1:
        headline += f"  (scenario {done_n + 1} of {total_n})"
    st.markdown(headline)

    if total_n > 1:
        st.progress(done_n / total_n, text=f"Scenarios complete: {done_n}/{total_n}")
    phase_done = sum(1 for _, s in phases if s == "done")
    st.progress(phase_done / len(phases), text=f"Current scenario: {phase_done}/{len(phases)} phases")

    for label, pstate in phases:
        icon, color = _PHASE_STYLE[pstate]
        suffix = ""
        if pstate == "running" and current_sub:
            suffix = f" — running `{current_sub}`"
        st.markdown(f":{color}[{icon} {label}]{suffix}")


def _failed_errors(state: dict) -> list[tuple[str, str]]:
    return [
        (key, rec["error"])
        for key, rec in sorted(state.get("tasks", {}).items())
        if rec.get("status") == "failed" and rec.get("error")
    ]


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def _status_header(phase: str, state: dict, log_text: str) -> None:
    if phase == "running":
        elapsed = _running_elapsed(state)
        label = "Running" + (f" · {elapsed} elapsed" if elapsed else "")
        st.badge(label, icon=":material/sync:", color="blue")
        st.caption(
            "Ray-tracing steps (rfluxmtx, rcontrib) can run for several minutes "
            "with no new log lines — that is normal, not a freeze."
        )
    elif phase == "complete":
        st.badge("Complete", icon=":material/check_circle:", color="green")
        st.caption("All tasks finished. Open the Results screen to view outputs.")
    elif phase == "failed":
        st.badge("Failed", icon=":material/error:", color="red")
        st.caption("A task failed. Polling stopped — details below.")
    elif phase == "crashed":
        st.badge("Stopped", icon=":material/warning:", color="red")
        st.caption(
            "The run process exited while a task was still running "
            "(killed or crashed). Polling stopped — log below."
        )
    else:
        st.badge("Ready", icon=":material/play_circle:", color="gray")
        st.caption("No run yet. Configure a stage above and launch.")


def _render_progress(state: dict, pid_running: bool, root: Path) -> str:
    phase = _run_phase(state, pid_running)
    log_text = read_run_log(root, tail_lines=400)

    with st.container(border=True):
        _status_header(phase, state, log_text)
        if phase == "running":
            _render_dds_tracker(state, log_text)
            if st.button("Stop run", icon=":material/stop_circle:", type="secondary"):
                stopped = stop_background_run(root)
                if stopped:
                    st.toast("Stopping run…", icon=":material/stop_circle:")
                else:
                    st.toast("No active run to stop.", icon=":material/info:")
                st.rerun()

    df = _task_rows(state)
    if not df.empty:
        with st.container(border=True):
            done = int((df["Status"] == "done").sum())
            running = int((df["Status"] == "running").sum())
            failed = int((df["Status"] == "failed").sum())
            with st.container(horizontal=True):
                st.metric("Done", done, border=True)
                st.metric("Running", running, border=True)
                st.metric("Failed", failed, border=True)
            st.dataframe(df, hide_index=True, width="stretch")

    if phase in ("failed", "crashed"):
        for key, err in _failed_errors(state):
            stage, _, scenario = key.partition(":")
            label = f"{_STAGE_LABELS.get(stage, stage)} · {scenario}"
            with st.expander(f"Error — {label}", icon=":material/error:", expanded=True):
                st.code(err, language="text")

    log_open = phase in ("failed", "crashed")
    with st.expander("Full log", icon=":material/terminal:", expanded=log_open):
        st.code("\n".join(log_text.splitlines()[-120:]) or "(no output yet)", language="text")

    updated = state.get("updated_at")
    if updated:
        st.caption(f"Run-state updated: {updated}")
    return phase


def render_run(project_dir: Path | None) -> None:
    st.markdown('<div class="material-header">Run</div>', unsafe_allow_html=True)

    if project_dir is None:
        st.warning("Complete Setup first — select a project directory.")
        return

    root = Path(project_dir)
    cfg_path = project_config_path(root)
    if not cfg_path.exists():
        st.error(f"Missing config: {cfg_path}")
        return

    # --- launch card -------------------------------------------------------- #
    with st.container(border=True):
        st.markdown("**Launch a run**")
        c1, c2 = st.columns([3, 1])
        with c1:
            stage_label = st.segmented_control(
                "Stage",
                list(_STAGE_CHOICES.keys()),
                default="All stages",
            )
        with c2:
            force = st.toggle("Force re-run", value=False, help="Ignore cached outputs")

        if st.button("Launch run", icon=":material/play_arrow:", type="primary"):
            stage = _STAGE_CHOICES.get(stage_label or "All stages", "all")
            try:
                pid = launch_background_run(root, stage=stage, force=force)
                st.toast(f"Run started (PID {pid})", icon=":material/rocket_launch:")
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))

        if _pid_running(root):
            st.caption(":green[●] A run is currently active.")
        else:
            st.caption(":gray[●] No active run.")

    # --- progress ----------------------------------------------------------- #
    st.markdown("##### Progress")

    state = _safe_status(cfg_path)
    if _run_phase(state, _pid_running(root)) == "running":

        @st.fragment(run_every="3s")
        def _live() -> None:
            live_state = _safe_status(cfg_path)
            live_pid = _pid_running(root)
            phase = _render_progress(live_state, live_pid, root)
            if phase != "running":
                # Run finished/failed — break out to a static report (stops polling).
                st.rerun()

        _live()
    else:
        _render_progress(state, _pid_running(root), root)
        if st.button("Refresh", icon=":material/refresh:"):
            st.rerun()
