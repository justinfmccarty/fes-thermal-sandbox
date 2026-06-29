"""Canopy engine registry. Add an engine = add a file + register here + set config.

    model:
      canopy_engine: li2023_ceb   # swap here, nowhere else
"""
from __future__ import annotations
from .base import CanopyEngine

_REGISTRY: dict[str, type[CanopyEngine]] = {}


def register(cls: type[CanopyEngine]) -> type[CanopyEngine]:
    _REGISTRY[cls.name] = cls
    return cls


def get_engine(name: str) -> CanopyEngine:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown canopy engine {name!r}. Registered: {list(_REGISTRY)}")
    return _REGISTRY[name]()


# Import concrete engines so they self-register (uncomment as ported):
# from . import li2023_ceb, legacy_leaf  # noqa: E402,F401
