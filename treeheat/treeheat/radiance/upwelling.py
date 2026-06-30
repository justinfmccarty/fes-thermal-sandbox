"""Upwelling (reflected) shortwave.

PORT FROM: src_archive/upwelling_calculator.py
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pandas as pd

from treeheat.io.grids import get_grid_materials_for_scenario, get_material_properties_for_grid

if TYPE_CHECKING:
    from treeheat.io.materials import MaterialDatabase

__all__ = [
    "calculate_upwelling",
    "calculate_upwelling_for_grid",
    "extract_grid_id_from_column",
]


def extract_grid_id_from_column(column_name: str, sensor_points=None) -> str | None:
    match = re.search(r"\{(\d+)\}", str(column_name))
    if match:
        return f"{int(match.group(1)):02d}"
    match = re.search(r"grid(\d+)", str(column_name), re.IGNORECASE)
    if match:
        return f"{int(match.group(1)):02d}"
    try:
        col_num = int(column_name)
        if sensor_points is not None and "grid_name" in sensor_points.columns:
            if col_num < len(sensor_points):
                grid_name = str(sensor_points.iloc[col_num].get("grid_name", ""))
                if grid_name:
                    match = re.search(r"\{(\d+)\}", grid_name)
                    if match:
                        return f"{int(match.group(1)):02d}"
                    match = re.search(r"grid(\d+)", grid_name, re.IGNORECASE)
                    if match:
                        return f"{int(match.group(1)):02d}"
    except (ValueError, IndexError):
        pass
    return None


def calculate_upwelling(
    direct_df: pd.DataFrame,
    diffuse_df: pd.DataFrame,
    grid_material_mapping: pd.DataFrame,
    scenario_id: str,
    material_db: MaterialDatabase,
    sensor_points=None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    grid_materials = get_grid_materials_for_scenario(scenario_id, grid_material_mapping)
    K_up_dir = pd.DataFrame(index=direct_df.index, columns=direct_df.columns, dtype=float)
    K_up_dif = pd.DataFrame(index=diffuse_df.index, columns=diffuse_df.columns, dtype=float)

    for col in direct_df.columns:
        grid_id = extract_grid_id_from_column(col, sensor_points)
        if grid_id is not None and grid_id in grid_materials:
            albedo = material_db.get_albedo(grid_materials[grid_id])
        else:
            albedo = 0.3
        K_up_dir[col] = albedo * direct_df[col]
        K_up_dif[col] = albedo * diffuse_df[col]

    return K_up_dir, K_up_dif


def calculate_upwelling_for_grid(
    K_down_dir: float,
    K_down_dif: float,
    grid_id: str,
    scenario_id: str,
    grid_material_mapping: pd.DataFrame,
    material_db: MaterialDatabase,
) -> tuple[float, float]:
    albedo, _ = get_material_properties_for_grid(
        grid_id, scenario_id, grid_material_mapping, material_db
    )
    return albedo * K_down_dir, albedo * K_down_dif
