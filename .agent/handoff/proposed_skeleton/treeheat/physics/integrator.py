"""Biophysical integrator — couples ground, surface, soil, and the canopy ENGINE.

PORT FROM: src_archive/biophysical_tree_stress.py (BiophysicalTreeStressCalculator).

Contract:
  - Per tree, per hour: assemble state, call the selected canopy engine, return
    leaf temperature + fluxes + surface/MRT.
  - MUST NOT import a concrete canopy model. It depends only on engines.base.CanopyEngine,
    obtained via engines.get_engine(config['model']['canopy_engine']).
  - This indirection is what makes an engine swap a one-line config change.
"""
from __future__ import annotations
from .engines import get_engine  # noqa: F401  (use at runtime)


def run_biophysics(*_a, **_k):
    raise NotImplementedError("Port from src_archive/biophysical_tree_stress.py")
