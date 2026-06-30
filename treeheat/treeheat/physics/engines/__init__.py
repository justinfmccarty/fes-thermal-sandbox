"""Canopy engine registry. Add an engine = add a file + register here + set config.

    model:
      canopy_engine: li2023_ceb   # swap here, nowhere else

Concrete engines are imported lazily inside get_engine() so ``import treeheat`` never
pulls optional heavy deps (e.g. scipy in Phase 3).
"""
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from .base import CanopyEngine

if TYPE_CHECKING:
    pass

_REGISTRY: dict[str, type[CanopyEngine]] = {}

_ENGINE_MODULES: dict[str, str] = {
    "li2023_ceb": "treeheat.physics.engines.li2023_ceb",
    "legacy_leaf": "treeheat.physics.engines.legacy_leaf",
}


def register(cls: type[CanopyEngine]) -> type[CanopyEngine]:
    _REGISTRY[cls.name] = cls
    return cls


def _ensure_engine_loaded(name: str) -> None:
    if name in _REGISTRY:
        return
    module_path = _ENGINE_MODULES.get(name)
    if module_path is None:
        return
    importlib.import_module(module_path)


def get_engine(name: str) -> CanopyEngine:
    _ensure_engine_loaded(name)
    if name not in _REGISTRY:
        known = sorted(_ENGINE_MODULES)
        raise KeyError(f"Unknown canopy engine {name!r}. Registered: {known}")
    return _REGISTRY[name]()


def registered_engine_names() -> list[str]:
    return sorted(_ENGINE_MODULES)
