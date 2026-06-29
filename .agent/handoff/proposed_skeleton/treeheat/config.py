"""Configuration access — the ONLY sanctioned source of parameters and paths.

PORT FROM: src_archive/config_locator.py (principle was right; enforce it everywhere).

Contract:
  - Two layers: config/defaults.yaml (defaults) overridden by config/config.yaml (run).
  - get_config() / get_path() are the only public accessors. No hardcoded defaults
    anywhere else in the codebase.
  - validate_config() runs at startup: fails LOUDLY on missing keys or non-existent
    paths. Relative paths resolve against the config-file directory (portable).
"""
from __future__ import annotations
from pathlib import Path
from typing import Any


def get_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load merged defaults + run config as a dict. TODO: implement."""
    raise NotImplementedError("Port from src_archive/config_locator.py")


def get_path(key: str) -> Path:
    """Resolve a config path key to an absolute Path. TODO: implement."""
    raise NotImplementedError


def validate_config(cfg: dict[str, Any]) -> None:
    """Fail loudly on missing keys / missing input files. TODO: implement."""
    raise NotImplementedError
