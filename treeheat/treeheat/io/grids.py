"""Sensor grids and grid->material mapping.

PORT FROM: src_archive/grid_material_mapping.py (minimal subset for upwelling/integrator)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from treeheat.config import get_path

if TYPE_CHECKING:
    from treeheat.io.materials import MaterialDatabase

__all__ = [
    "get_grid_materials_for_scenario",
    "get_material_properties_for_grid",
    "load_grid_material_mapping",
]


def load_grid_material_mapping(
    csv_path: str | Path | None = None,
    baseline_csv_path: str | Path | None = None,
    scenario_csv_path: str | Path | None = None,
    cfg: dict | None = None,
) -> pd.DataFrame:
    dfs: list[pd.DataFrame] = []

    if csv_path and os.path.exists(csv_path):
        dfs.append(pd.read_csv(csv_path))

    if baseline_csv_path and os.path.exists(baseline_csv_path):
        dfs.append(pd.read_csv(baseline_csv_path))

    if scenario_csv_path and os.path.exists(scenario_csv_path):
        scenario_df = pd.read_csv(scenario_csv_path)
        scenario_df = scenario_df[
            scenario_df["material_name"].notna() & (scenario_df["material_name"] != "")
        ]
        if len(scenario_df) > 0:
            dfs.append(scenario_df)

    if not dfs:
        if cfg is not None:
            baseline_csv_path = get_path("grid_material_mapping_file", cfg)
            scenario_csv_path = get_path("scenario_grid_materials_file", cfg)
            return load_grid_material_mapping(
                baseline_csv_path=baseline_csv_path,
                scenario_csv_path=scenario_csv_path,
            )
        raise FileNotFoundError(
            f"No grid-material mapping files found. "
            f"Checked: csv_path={csv_path}, baseline={baseline_csv_path}, scenario={scenario_csv_path}"
        )

    combined_df = pd.concat(dfs, ignore_index=True)
    required_cols = ["scenario_id", "grid_id", "material_name"]
    missing = [c for c in required_cols if c not in combined_df.columns]
    if missing:
        raise ValueError(f"Missing required columns in mapping file: {missing}")

    combined_df["grid_id"] = combined_df["grid_id"].astype(str).str.zfill(2)

    if baseline_csv_path and scenario_csv_path:
        baseline_ids = set(combined_df[combined_df["scenario_id"] == "baseline"].index)
        if len(baseline_ids) > 72:
            combined_df = combined_df.drop_duplicates(
                subset=["scenario_id", "grid_id"],
                keep="first",
            )

    return combined_df


def get_grid_materials_for_scenario(
    scenario_id: str,
    mapping_df: pd.DataFrame,
) -> dict[str, str]:
    scenario_data = mapping_df[mapping_df["scenario_id"] == scenario_id]
    if len(scenario_data) == 0:
        raise ValueError(f"No material assignments found for scenario: {scenario_id}")
    grid_materials: dict[str, str] = {}
    for _, row in scenario_data.iterrows():
        grid_id = str(row["grid_id"]).zfill(2)
        grid_materials[grid_id] = row["material_name"]
    return grid_materials


def get_material_properties_for_grid(
    grid_id: str,
    scenario_id: str,
    mapping_df: pd.DataFrame,
    material_db: MaterialDatabase,
) -> tuple[float, float]:
    grid_id = str(grid_id).zfill(2)
    scenario_data = mapping_df[
        (mapping_df["scenario_id"] == scenario_id) & (mapping_df["grid_id"] == grid_id)
    ]
    if len(scenario_data) == 0:
        material_name = "grey_concrete"
    else:
        material_name = scenario_data.iloc[0]["material_name"]
    return material_db.get_albedo(material_name), material_db.get_emissivity(material_name)
