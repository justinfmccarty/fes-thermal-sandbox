"""Background run launcher — survives Streamlit session refresh."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from treeheat.project import project_config_path

__all__ = [
    "launch_background_run",
    "stop_background_run",
    "read_run_log",
    "run_pid_path",
    "run_log_path",
    "is_process_running",
]


def outputs_root(project_dir: Path) -> Path:
    return project_dir.resolve() / "outputs"


def run_log_path(project_dir: Path) -> Path:
    return outputs_root(project_dir) / "run.log"


def run_pid_path(project_dir: Path) -> Path:
    return outputs_root(project_dir) / "run.pid"


def is_process_running(pid: int) -> bool:
    # The run is a child of the Streamlit process. When it exits it becomes a
    # zombie until reaped, and os.kill(pid, 0) reports a zombie as alive — which
    # would pin the UI on "running" forever. Reap it first if it's our child.
    try:
        reaped, _ = os.waitpid(pid, os.WNOHANG)
        if reaped == pid:
            return False
    except ChildProcessError:
        # Not our child (already reaped, or launched by a different process).
        pass
    except OSError:
        pass
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def launch_background_run(
    project_dir: Path | str,
    *,
    stage: str = "all",
    force: bool = False,
) -> int:
    """Start ``treeheat run`` detached; return PID."""
    root = Path(project_dir).resolve()
    cfg_path = project_config_path(root)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config not found: {cfg_path}")

    out_root = outputs_root(root)
    out_root.mkdir(parents=True, exist_ok=True)
    log_path = run_log_path(root)
    pid_path = run_pid_path(root)

    cmd = [
        sys.executable,
        "-u",  # unbuffered stdout/stderr so the log streams live to the UI
        "-m",
        "treeheat.cli",
        "run",
        stage,
        "--config",
        str(cfg_path),
    ]
    if force:
        cmd.append("--force")

    # PYTHONUNBUFFERED belt-and-suspenders alongside -u; without this the child
    # block-buffers stdout (it is a file, not a TTY) and the log appears frozen.
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    # Truncate so the log reflects only the current run (append stacked stale
    # runs together and made the tail confusing to read).
    log_handle = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=str(root),
        env=env,
    )
    log_handle.close()
    pid_path.write_text(str(proc.pid), encoding="utf-8")
    return proc.pid


def stop_background_run(project_dir: Path | str, *, timeout: float = 5.0) -> bool:
    """Terminate the active run and its Radiance children.

    The run is launched with ``start_new_session=True`` so it leads its own
    process group; signalling the group (``killpg``) takes down the Python
    runner *and* the spawned Radiance subprocesses. Sends SIGTERM, waits, then
    escalates to SIGKILL. Returns True if a process was signalled.
    """
    root = Path(project_dir)
    pid_path = run_pid_path(root)
    if not pid_path.exists():
        return False
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except ValueError:
        return False
    if not is_process_running(pid):
        return False

    def _signal_group(sig: int) -> None:
        try:
            os.killpg(os.getpgid(pid), sig)
        except ProcessLookupError:
            pass
        except OSError:
            # Fall back to signalling just the pid if the group lookup fails.
            try:
                os.kill(pid, sig)
            except OSError:
                pass

    _signal_group(signal.SIGTERM)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_process_running(pid):
            return True
        time.sleep(0.2)

    _signal_group(signal.SIGKILL)
    return True


def read_run_log(project_dir: Path | str, *, tail_lines: int = 40) -> str:
    path = run_log_path(Path(project_dir))
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-tail_lines:])
