"""Content-addressed fingerprints for skip-already-computed logic."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import treeheat

__all__ = [
    "code_version",
    "config_sha256",
    "content_hash",
    "file_fingerprint",
]

_SMALL_FILE_THRESHOLD = 10 * 1024 * 1024  # 10 MiB


def file_fingerprint(path: Path | str) -> str:
    """Return a stable fingerprint for a file or directory."""
    p = Path(path)
    if not p.exists():
        return f"missing:{p.name}"

    if p.is_dir():
        stat = p.stat()
        return f"dir:{stat.st_size}:{stat.st_mtime_ns}"

    stat = p.stat()
    if stat.st_size <= _SMALL_FILE_THRESHOLD:
        digest = hashlib.sha256()
        with p.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"

    return f"stat:{stat.st_size}:{stat.st_mtime_ns}"


def config_sha256(cfg: dict[str, Any]) -> str:
    """Hash the merged config dict (sorted JSON for stability)."""
    payload = json.dumps(cfg, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def content_hash(
    stage: str,
    scenario_id: str | None,
    cfg_subset: dict[str, Any],
    input_paths: dict[str, str | None],
) -> str:
    """Content-addressed hash for a pipeline task."""
    parts: list[str] = [stage, scenario_id or "all"]
    parts.append(json.dumps(cfg_subset, sort_keys=True, default=str))
    for key in sorted(input_paths):
        fp = input_paths[key]
        parts.append(f"{key}={fp or 'none'}")
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def code_version() -> tuple[str, str | None]:
    """Return (treeheat_version, git_commit_or_none)."""
    version = getattr(treeheat, "__version__", "0.0.0")
    commit: str | None = None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            commit = result.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        pass
    return version, commit
