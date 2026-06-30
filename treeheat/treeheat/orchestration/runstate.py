"""Machine-readable run-state on disk for CLI, UI, and resume."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from treeheat.orchestration.hashing import code_version, config_sha256

__all__ = ["RunState", "TaskRecord", "TaskStatus", "task_key"]

TaskStatus = Literal["pending", "running", "done", "failed"]
SCHEMA_VERSION = 1


def task_key(stage: str, scenario_id: str | None = None) -> str:
    return f"{stage}:{scenario_id if scenario_id else 'all'}"


@dataclass
class TaskRecord:
    status: TaskStatus = "pending"
    content_hash: str = ""
    outputs: list[str] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "content_hash": self.content_hash,
            "outputs": self.outputs,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskRecord:
        return cls(
            status=data.get("status", "pending"),
            content_hash=data.get("content_hash", ""),
            outputs=list(data.get("outputs", [])),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            error=data.get("error"),
        )


@dataclass
class RunState:
    schema_version: int = SCHEMA_VERSION
    config_path: str = ""
    config_sha256: str = ""
    treeheat_version: str = ""
    git_commit: str | None = None
    updated_at: str = ""
    tasks: dict[str, TaskRecord] = field(default_factory=dict)

    @classmethod
    def create(cls, config_path: Path | str, cfg: dict[str, Any]) -> RunState:
        version, commit = code_version()
        return cls(
            config_path=str(config_path),
            config_sha256=config_sha256(cfg),
            treeheat_version=version,
            git_commit=commit,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    def is_satisfied(self, key: str, content_hash: str) -> bool:
        rec = self.tasks.get(key)
        if rec is None:
            return False
        return rec.status == "done" and rec.content_hash == content_hash

    def mark_running(self, key: str, content_hash: str) -> None:
        self.tasks[key] = TaskRecord(
            status="running",
            content_hash=content_hash,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_done(self, key: str, content_hash: str, outputs: list[str | Path]) -> None:
        rec = self.tasks.get(key, TaskRecord())
        rec.status = "done"
        rec.content_hash = content_hash
        rec.outputs = [str(o) for o in outputs]
        rec.finished_at = datetime.now(timezone.utc).isoformat()
        rec.error = None
        self.tasks[key] = rec
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_failed(self, key: str, content_hash: str, error: str) -> None:
        rec = self.tasks.get(key, TaskRecord())
        rec.status = "failed"
        rec.content_hash = content_hash
        rec.finished_at = datetime.now(timezone.utc).isoformat()
        rec.error = error
        self.tasks[key] = rec
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "config_path": self.config_path,
            "config_sha256": self.config_sha256,
            "treeheat_version": self.treeheat_version,
            "git_commit": self.git_commit,
            "updated_at": self.updated_at,
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunState:
        tasks = {
            k: TaskRecord.from_dict(v) for k, v in data.get("tasks", {}).items()
        }
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            config_path=data.get("config_path", ""),
            config_sha256=data.get("config_sha256", ""),
            treeheat_version=data.get("treeheat_version", ""),
            git_commit=data.get("git_commit"),
            updated_at=data.get("updated_at", ""),
            tasks=tasks,
        )

    @classmethod
    def load(cls, path: Path) -> RunState:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp, path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
