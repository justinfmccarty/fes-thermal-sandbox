"""Sensor grids and grid->material mapping.

PORT FROM: src_archive/grid_material_mapping.py + grid_records/

Contract:
  - map grid IDs (00..71) -> material assignment per scenario.\n  - baseline grid (dense) vs scenario grid (sparse/fast). Guard sensor-count == feather rows.
"""
from __future__ import annotations


def _todo(*_a, **_k):
    raise NotImplementedError("Placeholder — port logic from the archive file above.")
