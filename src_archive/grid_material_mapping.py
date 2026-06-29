"""
Grid-Material Mapping Module

Manages scenario-specific assignments of materials to grid points.
Each scenario has different material assignments for grid IDs (00, 01, ... 71).
"""

import pandas as pd
import os
from typing import Dict, Optional, Tuple
import numpy as np


def load_grid_material_mapping(
    csv_path: str = None,
    baseline_csv_path: str = None,
    scenario_csv_path: str = None
) -> pd.DataFrame:
    """
    Load grid-material mapping from CSV file(s).
    
    Can load from:
    - Single combined file (csv_path)
    - Separate baseline and scenario files (baseline_csv_path, scenario_csv_path)
    
    Expected CSV structure:
    scenario_id,grid_id,material_name,area_m2,ground_or_facade
    baseline,00,grey_concrete,125.5,ground
    baseline,01,grey_asphalt,98.3,ground
    baseline,00,grey_asphalt,388.29,facade
    scenario_001,00,short_grass,125.5,ground
    ...
    
    Note: The 'ground_or_facade' column is REQUIRED. It indicates whether each grid point
    represents a ground/landscape surface ('ground') or facade surface ('facade'). This is
    essential for the scenario workflow, which independently modifies landscape and facade
    surfaces based on the instruction tuple (landscape_naturalness, facade_naturalness).
    
    Args:
        csv_path: Path to combined scenario_grid_materials.csv (if using single file)
        baseline_csv_path: Path to baseline_materials.csv (if using separate files)
        scenario_csv_path: Path to scenario_grid_materials.csv (if using separate files)
        
    Returns:
        DataFrame with columns: scenario_id, grid_id, material_name, area_m2, 
        and ground_or_facade (required for scenario workflows)
    """
    dfs = []
    
    # Load from single file if provided
    if csv_path and os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        dfs.append(df)
    
    # Load from separate files if provided
    if baseline_csv_path and os.path.exists(baseline_csv_path):
        baseline_df = pd.read_csv(baseline_csv_path)
        dfs.append(baseline_df)
    
    if scenario_csv_path and os.path.exists(scenario_csv_path):
        scenario_df = pd.read_csv(scenario_csv_path)
        # Filter out empty rows (scenarios with no material_name)
        scenario_df = scenario_df[scenario_df['material_name'].notna() & (scenario_df['material_name'] != '')]
        if len(scenario_df) > 0:
            dfs.append(scenario_df)
    
    if not dfs:
        raise FileNotFoundError(
            f"No grid-material mapping files found. "
            f"Checked: csv_path={csv_path}, baseline_csv_path={baseline_csv_path}, "
            f"scenario_csv_path={scenario_csv_path}"
        )
    
    # Combine all DataFrames
    combined_df = pd.concat(dfs, ignore_index=True)
    
    # Validate required columns
    required_cols = ['scenario_id', 'grid_id', 'material_name']
    missing_cols = [col for col in required_cols if col not in combined_df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in mapping file: {missing_cols}")
    
    # Ensure grid_id is string (pad with zeros if needed)
    combined_df['grid_id'] = combined_df['grid_id'].astype(str).str.zfill(2)
    
    # Remove duplicates (baseline from template file if also in baseline file)
    # Keep baseline entries from baseline_csv_path if both exist
    if baseline_csv_path and scenario_csv_path:
        # Remove baseline entries from scenario file if they exist in baseline file
        baseline_ids = set(combined_df[combined_df['scenario_id'] == 'baseline'].index)
        if len(baseline_ids) > 72:  # More than expected, likely duplicates
            # Keep only first occurrence of each baseline grid
            combined_df = combined_df.drop_duplicates(
                subset=['scenario_id', 'grid_id'],
                keep='first'
            )
    
    return combined_df


def get_grid_materials_for_scenario(scenario_id: str, mapping_df: pd.DataFrame) -> Dict[str, str]:
    """
    Get material assignments for all grids in a scenario.
    
    Args:
        scenario_id: Scenario identifier (e.g., 'baseline', 'scenario_001')
        mapping_df: DataFrame from load_grid_material_mapping()
        
    Returns:
        Dictionary mapping grid_id -> material_name
    """
    scenario_data = mapping_df[mapping_df['scenario_id'] == scenario_id]
    
    if len(scenario_data) == 0:
        raise ValueError(f"No material assignments found for scenario: {scenario_id}")
    
    # Create dictionary
    grid_materials = {}
    for _, row in scenario_data.iterrows():
        grid_id = str(row['grid_id']).zfill(2)
        material_name = row['material_name']
        grid_materials[grid_id] = material_name
    
    return grid_materials


def get_material_properties_for_grid(
    grid_id: str,
    scenario_id: str,
    mapping_df: pd.DataFrame,
    material_db
) -> Tuple[float, float]:
    """
    Get material properties (albedo, emissivity) for a specific grid in a scenario.
    
    Args:
        grid_id: Grid identifier (e.g., '00', '01')
        scenario_id: Scenario identifier
        mapping_df: DataFrame from load_grid_material_mapping()
        material_db: MaterialDatabase instance
        
    Returns:
        Tuple of (albedo, emissivity)
    """
    grid_id = str(grid_id).zfill(2)
    
    # Get material name for this grid
    scenario_data = mapping_df[
        (mapping_df['scenario_id'] == scenario_id) &
        (mapping_df['grid_id'] == grid_id)
    ]
    
    if len(scenario_data) == 0:
        # Default material if not found
        material_name = 'grey_concrete'
    else:
        material_name = scenario_data.iloc[0]['material_name']
    
    # Get properties from material database
    albedo = material_db.get_albedo(material_name)
    emissivity = material_db.get_emissivity(material_name)
    
    return albedo, emissivity


def get_grid_area(grid_id: str, scenario_id: str, mapping_df: pd.DataFrame) -> float:
    """
    Get area for a specific grid.
    
    Args:
        grid_id: Grid identifier
        scenario_id: Scenario identifier
        mapping_df: DataFrame from load_grid_material_mapping()
        
    Returns:
        Area [m2], or 0.0 if not found
    """
    grid_id = str(grid_id).zfill(2)
    
    scenario_data = mapping_df[
        (mapping_df['scenario_id'] == scenario_id) &
        (mapping_df['grid_id'] == grid_id)
    ]
    
    if len(scenario_data) > 0 and 'area_m2' in scenario_data.columns:
        area = scenario_data.iloc[0]['area_m2']
        if pd.notna(area):
            return float(area)
    
    return 0.0


def get_grid_surface_type(grid_id: str, scenario_id: str, mapping_df: pd.DataFrame) -> Optional[str]:
    """
    Get the surface type (ground or facade) for a specific grid.
    
    This is REQUIRED for scenario workflows, which independently modify landscape and 
    facade surfaces based on instruction tuples (landscape_naturalness, facade_naturalness).
    
    Args:
        grid_id: Grid identifier (e.g., '00', '01')
        scenario_id: Scenario identifier (e.g., 'baseline', 'scenario_001')
        mapping_df: DataFrame from load_grid_material_mapping()
        
    Returns:
        'ground', 'facade', or None if not found or column doesn't exist
    """
    grid_id = str(grid_id).zfill(2)
    
    if 'ground_or_facade' not in mapping_df.columns:
        return None
    
    scenario_data = mapping_df[
        (mapping_df['scenario_id'] == scenario_id) &
        (mapping_df['grid_id'] == grid_id)
    ]
    
    if len(scenario_data) > 0:
        surface_type = scenario_data.iloc[0].get('ground_or_facade')
        if pd.notna(surface_type):
            return str(surface_type).lower()
    
    return None


def update_scenario_grid_mapping(
    scenario_id: str,
    instruction: Tuple[float, float],
    landscape_material: str,
    facade_material: str,
    csv_path: str
):
    """
    Update scenario grid-material mapping CSV with material assignments.
    
    Note: This is a placeholder function. Full implementation requires:
    1. Mapping Radiance surface IDs to grid IDs (from column names in feather files)
    2. Determining which grids correspond to landscape vs facade surfaces
    
    For now, this function updates the CSV with the instruction and materials used,
    but the actual grid-material mapping will need to be determined from Radiance outputs.
    
    If the CSV contains a 'ground_or_facade' column (from baseline_materials.csv),
    this information should be preserved when updating scenario mappings.
    
    Args:
        scenario_id: Scenario identifier (e.g., 'scenario_001')
        instruction: (landscape_naturalness, facade_naturalness) tuple
        landscape_material: Material name used for landscape surfaces
        facade_material: Material name used for facade surfaces
        csv_path: Path to scenario_grid_materials.csv
    """
    if not os.path.exists(csv_path):
        print(f"Warning: Scenario mapping file not found: {csv_path}")
        return
    
    try:
        # Load existing CSV
        df = pd.read_csv(csv_path)
        
        # Update rows for this scenario
        scenario_mask = df['scenario_id'] == scenario_id
        
        if scenario_mask.sum() == 0:
            print(f"Warning: No rows found for scenario {scenario_id} in {csv_path}")
            return
        
        # For now, we can't determine which grids got which materials without
        # parsing the Radiance output column names. This is a placeholder.
        # The actual mapping should be done by analyzing the feather file column names
        # and matching them to grid IDs.
        
        # Store instruction and materials as metadata (could add metadata columns)
        print(f"Note: Scenario {scenario_id} used landscape_material={landscape_material}, "
              f"facade_material={facade_material}, instruction={instruction}")
        print(f"      Grid-material mapping will be determined from Radiance output column names")
        
    except Exception as e:
        print(f"Warning: Could not update scenario grid mapping: {e}")


def create_template_csv(output_path: str, n_grids: int = 72, default_material: str = 'grey_concrete'):
    """
    Create a template CSV file for grid-material mappings.
    
    Args:
        output_path: Path to save template CSV
        n_grids: Number of grids (default 72 for 00-71)
        default_material: Default material name for baseline
    """
    rows = []
    
    # Create baseline scenario with all grids
    for i in range(n_grids):
        grid_id = f"{i:02d}"
        rows.append({
            'scenario_id': 'baseline',
            'grid_id': grid_id,
            'material_name': default_material,
            'area_m2': 0.0  # User should fill in
        })
    
    # Create placeholder rows for scenarios (user can add more)
    for scenario_num in range(1, 11):  # scenario_001 to scenario_010
        scenario_id = f'scenario_{scenario_num:03d}'
        for i in range(n_grids):
            grid_id = f"{i:02d}"
            rows.append({
                'scenario_id': scenario_id,
                'grid_id': grid_id,
                'material_name': '',  # Empty for user to fill
                'area_m2': 0.0
            })
    
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"Created template CSV at: {output_path}")
    print(f"Template includes baseline scenario and 10 placeholder scenarios.")
    print(f"Please fill in material_name and area_m2 columns for each scenario.")

