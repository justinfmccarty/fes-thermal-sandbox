"""Generate per-scenario grid→material assignments.

PORT FROM: src_archive/populate_scenario_materials.py

The biophysics upwelling term needs, for each scenario, the material at every
sensor-grid point (to look up albedo). That table is fully *derived* from three
inputs already in the project:

- the baseline grid→material mapping (``baseline_materials.csv``),
- the scenario instructions in config (``simulation.instructions``), and
- the naturalness material catalog (material DB + base library).

It uses the SAME deterministic seed (md5 of the scenario id) and the SAME
three-tier coverage logic as the raytrace material swap, so the grid assignment
is consistent with the geometry assignment. This is a bookkeeping step — no
Radiance involved — so it can run independently of (and before) ray tracing.
"""

from __future__ import annotations

import hashlib
import random
from pathlib import Path
from typing import Any

import pandas as pd

from treeheat.config import get_config, get_path
from treeheat.io.materials import load_material_database

__all__ = [
    "build_scenario_grid_materials",
    "write_scenario_grid_materials",
    "scenario_rows_present",
]

_REQUIRED_BASELINE_COLS = ("grid_id", "material_name", "ground_or_facade")


def scenario_rows_present(cfg: dict[str, Any]) -> bool:
    """True if the scenario grid-materials file already has non-baseline rows."""
    path = get_path("scenario_grid_materials_file", cfg)
    if not Path(path).exists():
        return False
    try:
        df = pd.read_csv(path)
    except (pd.errors.EmptyDataError, OSError):
        return False
    if "scenario_id" not in df.columns:
        return False
    return bool((df["scenario_id"].astype(str) != "baseline").any())


def build_scenario_grid_materials(cfg: dict[str, Any] | None = None) -> pd.DataFrame:
    """Derive the full baseline + per-scenario grid→material table."""
    if cfg is None:
        cfg = get_config()

    # Local import keeps the io/pipeline boundary clean (catalog lives in raytrace).
    from treeheat.pipeline.raytrace import NaturalnessMaterialCatalog

    baseline_path = Path(get_path("grid_material_mapping_file", cfg))
    if not baseline_path.exists():
        raise FileNotFoundError(
            f"Baseline grid materials not found: {baseline_path}. "
            "Provide inputs/grid_records/baseline_materials.csv before generating "
            "scenario grid materials."
        )
    baseline_df = pd.read_csv(baseline_path)
    missing = [c for c in _REQUIRED_BASELINE_COLS if c not in baseline_df.columns]
    if missing:
        raise ValueError(
            f"{baseline_path.name} is missing required columns {missing}; "
            f"found {list(baseline_df.columns)}"
        )

    material_db = load_material_database(cfg=cfg)
    mat_path = get_path("material_database_file", cfg)
    base_lib = mat_path.parent / "base_material_library.txt"
    catalog = NaturalnessMaterialCatalog(material_db, base_lib)

    instructions = cfg.get("simulation", {}).get("instructions", [])
    has_area = "area_m2" in baseline_df.columns

    def _row(scenario_id: str, src: pd.Series, material: str) -> dict[str, Any]:
        row: dict[str, Any] = {
            "scenario_id": scenario_id,
            "grid_id": src["grid_id"],
            "material_name": material,
        }
        if has_area:
            row["area_m2"] = src["area_m2"]
        row["ground_or_facade"] = src["ground_or_facade"]
        return row

    rows: list[dict[str, Any]] = [
        _row("baseline", src, src["material_name"]) for _, src in baseline_df.iterrows()
    ]

    ground_idx = list(baseline_df[baseline_df["ground_or_facade"] == "ground"].index)
    facade_idx = list(baseline_df[baseline_df["ground_or_facade"] == "facade"].index)
    n_ground, n_facade = len(ground_idx), len(facade_idx)

    for i, instr in enumerate(instructions):
        scenario_id = f"scenario_{i:03d}"
        landscape_ratio, facade_ratio = float(instr[0]), float(instr[1])

        seed = int(hashlib.md5(scenario_id.encode()).hexdigest(), 16) % (2**32)
        random.seed(seed)

        l_lower, l_upper, l_cov = catalog.calculate_three_tier_coverage(
            landscape_ratio, "landscape"
        )
        f_lower, f_upper, f_cov = catalog.calculate_three_tier_coverage(
            facade_ratio, "facade"
        )

        n_ground_upper = int(n_ground * l_cov)
        n_facade_upper = int(n_facade * f_cov)

        ground_upper = random.sample(ground_idx, n_ground_upper) if n_ground_upper else []
        ground_lower = [idx for idx in ground_idx if idx not in ground_upper]
        facade_upper = random.sample(facade_idx, n_facade_upper) if n_facade_upper else []
        facade_lower = [idx for idx in facade_idx if idx not in facade_upper]

        for idx_list, material in (
            (ground_upper, l_upper),
            (ground_lower, l_lower),
            (facade_upper, f_upper),
            (facade_lower, f_lower),
        ):
            for idx in idx_list:
                rows.append(_row(scenario_id, baseline_df.loc[idx], material))

    return pd.DataFrame(rows)


def write_scenario_grid_materials(
    cfg: dict[str, Any] | None = None,
    *,
    path: str | Path | None = None,
) -> Path:
    """Build and write the scenario grid-materials CSV; return its path."""
    if cfg is None:
        cfg = get_config()
    df = build_scenario_grid_materials(cfg)
    out = Path(path) if path else Path(get_path("scenario_grid_materials_file", cfg))
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return out
