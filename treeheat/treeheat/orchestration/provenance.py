"""Provenance sidecars for auditable, re-runnable outputs."""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from treeheat.orchestration.hashing import code_version

__all__ = ["Provenance", "provenance_path", "write_provenance"]


def provenance_path(outputs_root: Path, stage: str, scenario_id: str | None) -> Path:
    """Central provenance dir under outputs/ (avoids writing next to read-only inputs)."""
    sid = scenario_id if scenario_id else "all"
    return outputs_root / "provenance" / stage / f"{sid}.json"


@dataclass
class Provenance:
    treeheat_version: str
    git_commit: str | None
    python_version: str
    platform: str
    utc_timestamp: str
    stage: str
    scenario_id: str | None
    canopy_engine: str
    content_hash: str
    config_path: str
    config_sha256: str
    input_fingerprints: dict[str, str] = field(default_factory=dict)
    output_paths: list[str] = field(default_factory=list)

    @classmethod
    def build(
        cls,
        *,
        stage: str,
        scenario_id: str | None,
        canopy_engine: str,
        content_hash: str,
        config_path: Path | str,
        config_sha256: str,
        input_fingerprints: dict[str, str] | None = None,
        output_paths: list[str | Path] | None = None,
    ) -> Provenance:
        version, commit = code_version()
        return cls(
            treeheat_version=version,
            git_commit=commit,
            python_version=sys.version.split()[0],
            platform=platform.platform(),
            utc_timestamp=datetime.now(timezone.utc).isoformat(),
            stage=stage,
            scenario_id=scenario_id,
            canopy_engine=canopy_engine,
            content_hash=content_hash,
            config_path=str(config_path),
            config_sha256=config_sha256,
            input_fingerprints=input_fingerprints or {},
            output_paths=[str(p) for p in (output_paths or [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def write_provenance(prov: Provenance, outputs_root: Path) -> Path:
    """Write provenance JSON and return the path."""
    path = provenance_path(outputs_root, prov.stage, prov.scenario_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prov.to_dict(), indent=2), encoding="utf-8")
    return path
