"""
Upwelling Shortwave Calculator

Calculates upwelling (reflected) shortwave radiation from downwelling radiation
and material albedo properties. Uses grid-material mapping to determine
material for each sensor point.
"""

import pandas as pd
import numpy as np
from typing import Tuple
from grid_material_mapping import get_grid_materials_for_scenario, get_material_properties_for_grid


def calculate_upwelling(
    direct_df: pd.DataFrame,
    diffuse_df: pd.DataFrame,
    grid_material_mapping: pd.DataFrame,
    scenario_id: str,
    material_db,
    sensor_points=None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calculate upwelling shortwave radiation (K_up) from downwelling radiation.
    
    For each grid point:
    - K_up_dir = albedo_surface * K_down_dir
    - K_up_dif = albedo_surface * K_down_dif
    
    Args:
        direct_df: DataFrame with direct downwelling SW [W/m2], sensors as columns, hours as rows
        diffuse_df: DataFrame with diffuse downwelling SW [W/m2], sensors as columns, hours as rows
        grid_material_mapping: DataFrame from load_grid_material_mapping()
        scenario_id: Scenario identifier
        material_db: MaterialDatabase instance
        sensor_points: Optional DataFrame with sensor points (to map numeric column indices to grid_name)
        
    Returns:
        Tuple of (K_up_dir, K_up_dif) DataFrames matching input structure
    """
    # Get material assignments for this scenario
    grid_materials = get_grid_materials_for_scenario(scenario_id, grid_material_mapping)
    
    # Initialize output DataFrames with same structure as input
    K_up_dir = pd.DataFrame(index=direct_df.index, columns=direct_df.columns, dtype=float)
    K_up_dif = pd.DataFrame(index=diffuse_df.index, columns=diffuse_df.columns, dtype=float)
    
    # Process each sensor column
    for col_idx, col in enumerate(direct_df.columns):
        # Extract grid ID from column name
        # Column names might be like "grid00_tall_grass" or just sensor indices
        grid_id = extract_grid_id_from_column(col, sensor_points)
        
        # Get material properties for this grid
        if grid_id is not None and grid_id in grid_materials:
            material_name = grid_materials[grid_id]
            albedo = material_db.get_albedo(material_name)
        else:
            # Default albedo if grid not found
            albedo = 0.3
        
        # Calculate upwelling radiation
        K_up_dir[col] = albedo * direct_df[col]
        K_up_dif[col] = albedo * diffuse_df[col]
    
    return K_up_dir, K_up_dif


def extract_grid_id_from_column(column_name: str, sensor_points=None) -> str:
    """
    Extract grid ID from column name.
    
    Column names might be:
    - "grid00_tall_grass" -> "00"
    - "{0}" -> "00" (curly brace format from sensor files)
    - "0" (numeric sensor index) -> extract from sensor_points if provided
    - Grid ID might be embedded in name
    
    Args:
        column_name: Column name from DataFrame
        sensor_points: Optional DataFrame with sensor points (to map numeric indices to grid_name)
        
    Returns:
        Grid ID string (e.g., "00", "01") or None if not found
    """
    # Try to find grid pattern in column name
    import re
    
    # Look for curly braces with number: {0}, {1}, etc.
    match = re.search(r'\{(\d+)\}', str(column_name))
    if match:
        grid_num = int(match.group(1))
        return f"{grid_num:02d}"
    
    # Look for "grid" followed by digits
    match = re.search(r'grid(\d+)', str(column_name), re.IGNORECASE)
    if match:
        grid_num = int(match.group(1))
        return f"{grid_num:02d}"
    
    # If column is just a number, try to map it to sensor_points if provided
    try:
        col_num = int(column_name)
        if sensor_points is not None and 'grid_name' in sensor_points.columns:
            # Map numeric column index to sensor_points row position
            if col_num < len(sensor_points):
                grid_name = str(sensor_points.iloc[col_num].get('grid_name', ''))
                if grid_name:
                    # Extract grid_id from grid_name format (e.g., "{0}" -> "00")
                    # Try curly brace pattern first
                    match = re.search(r'\{(\d+)\}', grid_name)
                    if match:
                        grid_num = int(match.group(1))
                        return f"{grid_num:02d}"
                    # Try gridXX pattern
                    match = re.search(r'grid(\d+)', grid_name, re.IGNORECASE)
                    if match:
                        grid_num = int(match.group(1))
                        return f"{grid_num:02d}"
    except (ValueError, IndexError):
        pass
    
    # If column is just a number and no sensor_points provided, return None
    return None


def calculate_upwelling_for_grid(
    K_down_dir: float,
    K_down_dif: float,
    grid_id: str,
    scenario_id: str,
    grid_material_mapping: pd.DataFrame,
    material_db
) -> Tuple[float, float]:
    """
    Calculate upwelling radiation for a single grid point.
    
    Args:
        K_down_dir: Direct downwelling SW [W/m2]
        K_down_dif: Diffuse downwelling SW [W/m2]
        grid_id: Grid identifier
        scenario_id: Scenario identifier
        grid_material_mapping: DataFrame from load_grid_material_mapping()
        material_db: MaterialDatabase instance
        
    Returns:
        Tuple of (K_up_dir, K_up_dif) [W/m2]
    """
    from grid_material_mapping import get_material_properties_for_grid
    
    albedo, _ = get_material_properties_for_grid(
        grid_id, scenario_id, grid_material_mapping, material_db
    )
    
    K_up_dir = albedo * K_down_dir
    K_up_dif = albedo * K_down_dif
    
    return K_up_dir, K_up_dif

