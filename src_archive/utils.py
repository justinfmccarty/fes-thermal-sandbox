"""
Utility functions for the Material Scenario Workflow
"""

import os
import glob
import pandas as pd
import numpy as np
from typing import Tuple, Optional


def reconstruct_scenario_feather_files(raytracing_results_dir):
    """
    Reconstruct scenario_feather_files dict from existing feather files.
    
    Returns:
        Dict with scenario_id as keys and dict values containing:
        - 'direct': path to direct feather file
        - 'diffuse': path to diffuse feather file  
        - 'instruction': (landscape_ratio, facade_ratio) tuple
    """
    scenario_feather_files = {}
    
    # Find all direct feather files
    direct_files = glob.glob(os.path.join(raytracing_results_dir, 'scenario_*_direct.feather'))
    
    for direct_path in sorted(direct_files):
        # Extract scenario_id from filename
        filename = os.path.basename(direct_path)
        scenario_id = filename.replace('_direct.feather', '')
        
        # Find corresponding diffuse file
        diffuse_path = direct_path.replace('_direct.feather', '_diffuse.feather')
        
        # Both must exist
        if os.path.exists(direct_path) and os.path.exists(diffuse_path):
            # Extract scenario number to get instruction
            scenario_num = int(scenario_id.split('_')[1])
            
            # Reconstruct instruction (matches workflow.py logic)
            row = scenario_num // 5
            col = scenario_num % 5
            landscape_ratio = col * 0.25
            facade_ratio = row * 0.25
            instruction = (landscape_ratio, facade_ratio)
            
            # Simplified structure - just what we need
            scenario_feather_files[scenario_id] = {
                'direct': direct_path,
                'diffuse': diffuse_path,
                'instruction': instruction
            }
    
    return scenario_feather_files

def load_tree_points(filepath: str) -> pd.DataFrame:
    """
    Load tree points from CSV file.
    
    Args:
        filepath: Path to CSV file with tree points
        
    Returns:
        DataFrame with xcoord, ycoord, zcoord, and tree_id columns
    """
    df = pd.read_csv(filepath)
    
    # Handle different column name formats (x_coord vs xcoord)
    if 'x_coord' in df.columns:
        df = df.rename(columns={
            'x_coord': 'xcoord',
            'y_coord': 'ycoord',
            'z_coord': 'zcoord'
        })
    
    # Ensure required columns exist
    required_cols = ['xcoord', 'ycoord', 'zcoord']
    if not all(col in df.columns for col in required_cols):
        raise ValueError(f"Tree points file must contain: {required_cols} (or x_coord/y_coord/z_coord)")
    
    # Add tree_id if not present
    if 'tree_id' not in df.columns:
        if 'number' in df.columns:
            df['tree_id'] = df['number']
        else:
            df['tree_id'] = range(len(df))
    
    # Filter to baseline scenario if scenario_id column exists
    if 'scenario_id' in df.columns:
        df = df[df['scenario_id'] == 'baseline'].copy()
    
    return df


def load_sensor_points(filepath: str) -> pd.DataFrame:
    """
    Load sensor points from CSV or Radiance .pts file.
    
    Args:
        filepath: Path to CSV or .pts file with sensor points
        
    Returns:
        DataFrame with xcoord, ycoord, zcoord columns
    """
    # Check file extension
    if filepath.endswith('.pts'):
        # Radiance .pts format: x y z dx dy dz (space-separated)
        df = pd.read_csv(filepath, sep=r'\s+', header=None, 
                        names=['xcoord', 'ycoord', 'zcoord', 'dx', 'dy', 'dz'])
        return df[['xcoord', 'ycoord', 'zcoord']]
    else:
        # CSV format
        df = pd.read_csv(filepath)
        
        # Handle different column name formats
        if 'x_coord' in df.columns:
            df = df.rename(columns={
                'x_coord': 'xcoord',
                'y_coord': 'ycoord',
                'z_coord': 'zcoord'
            })
        
        # Ensure required columns exist
        required_cols = ['xcoord', 'ycoord', 'zcoord']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"Sensor points file must contain: {required_cols}")
        
        # Preserve additional columns like grid_name if they exist (needed for grid material mapping)
        output_cols = required_cols.copy()
        if 'grid_name' in df.columns:
            output_cols.append('grid_name')
        if 'ghp_tree' in df.columns:
            output_cols.append('ghp_tree')
        
        return df[output_cols]


def find_warmest_day(
    irradiance_data: pd.DataFrame,
    month: int = 7,
    use_max: bool = True
) -> Tuple[int, int]:
    """
    Find the warmest day in a given month.
    
    Args:
        irradiance_data: DataFrame with sensors as columns, hours as rows
        month: Month number (1-12)
        use_max: If True, use maximum irradiance; if False, use mean
        
    Returns:
        Tuple of (start_hour, end_hour) for the warmest day
    """
    # Calculate hours for the month
    # Assuming Jan 1 = hour 0
    days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    month_start = sum(days_per_month[:month-1]) * 24
    month_end = month_start + (days_per_month[month-1] * 24) - 1
    
    month_data = irradiance_data.iloc[month_start:month_end+1, :]
    
    # Find day with maximum total irradiance
    daily_totals = []
    for day_start in range(0, len(month_data), 24):
        day_data = month_data.iloc[day_start:day_start+24, :]
        if use_max:
            daily_totals.append(day_data.max().max())
        else:
            daily_totals.append(day_data.sum().sum())
    
    warmest_day_idx = np.argmax(daily_totals)
    warmest_day_hour = month_start + (warmest_day_idx * 24)
    
    return (warmest_day_hour, warmest_day_hour + 23)


def save_results(
    results: dict,
    output_dir: str,
    prefix: str = "scenario"
):
    """
    Save workflow results to files.
    
    Args:
        results: Results dictionary from workflow
        output_dir: Output directory path
        prefix: Prefix for output files
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Save scenario impacts summary
    if results.get('risk_analyses'):
        impact_summary = []
        for scenario_id, risk_df in results['risk_analyses'].items():
            impact_summary.append({
                'scenario_id': scenario_id,
                'landscape_ratio': results['scenarios'][scenario_id]['instruction'][0],
                'facade_ratio': results['scenarios'][scenario_id]['instruction'][1],
                'avg_stress_reduction': risk_df['stress_reduction'].mean(),
                'max_stress_reduction': risk_df['stress_reduction'].max(),
                'min_stress_reduction': risk_df['stress_reduction'].min(),
                'std_stress_reduction': risk_df['stress_reduction'].std(),
                'trees_benefited': (risk_df['stress_reduction'] > 0).sum(),
                'trees_harmed': (risk_df['stress_reduction'] < 0).sum(),
                'total_trees': len(risk_df),
                'avg_percent_reduction': risk_df['percent_reduction'].mean()
            })
        
        summary_df = pd.DataFrame(impact_summary)
        summary_df = summary_df.sort_values('avg_stress_reduction', ascending=False)
        summary_df.to_csv(
            os.path.join(output_dir, f'{prefix}_impacts_summary.csv'),
            index=False
        )
        
        # Save individual risk analyses
        for scenario_id, risk_df in results['risk_analyses'].items():
            risk_df.to_csv(
                os.path.join(output_dir, f'{prefix}_{scenario_id}_risk_analysis.csv'),
                index=False
            )
    
    print(f"\nResults saved to: {output_dir}")


def validate_inputs(
    radiance_project_dir: str,
    tree_points_file: Optional[str] = None,
    sensor_points_file: Optional[str] = None,
    weather_file: Optional[str] = None
) -> dict:
    """
    Validate input files and directories.
    
    Args:
        radiance_project_dir: Path to radiance project directory
        tree_points_file: Path to tree points CSV
        sensor_points_file: Path to sensor points CSV
        weather_file: Path to weather EPW file
        
    Returns:
        Dictionary with validation results
    """
    validation = {
        'radiance_project': False,
        'tree_points': False,
        'sensor_points': False,
        'weather_file': False,
        'errors': []
    }
    
    # Check radiance project
    if os.path.exists(radiance_project_dir):
        scene_dir = os.path.join(radiance_project_dir, 'model', 'scene')
        if os.path.exists(scene_dir):
            validation['radiance_project'] = True
        else:
            validation['errors'].append(f"Scene directory not found: {scene_dir}")
    else:
        validation['errors'].append(f"Radiance project directory not found: {radiance_project_dir}")
    
    # Check tree points
    if tree_points_file:
        if os.path.exists(tree_points_file):
            try:
                df = pd.read_csv(tree_points_file, nrows=1)
                if all(col in df.columns for col in ['xcoord', 'ycoord', 'zcoord']):
                    validation['tree_points'] = True
                else:
                    validation['errors'].append("Tree points file missing required columns: xcoord, ycoord, zcoord")
            except Exception as e:
                validation['errors'].append(f"Error reading tree points file: {e}")
        else:
            validation['errors'].append(f"Tree points file not found: {tree_points_file}")
    
    # Check sensor points
    if sensor_points_file:
        if os.path.exists(sensor_points_file):
            try:
                df = pd.read_csv(sensor_points_file, nrows=1)
                required = ['xcoord', 'ycoord', 'zcoord']
                has_underscore = all(col in df.columns for col in ['x_coord', 'y_coord', 'z_coord'])
                has_no_underscore = all(col in df.columns for col in required)
                if has_underscore or has_no_underscore:
                    validation['sensor_points'] = True
                else:
                    validation['errors'].append("Sensor points file missing required columns: xcoord/x_coord, ycoord/y_coord, zcoord/z_coord")
            except Exception as e:
                validation['errors'].append(f"Error reading sensor points file: {e}")
        else:
            validation['errors'].append(f"Sensor points file not found: {sensor_points_file}")
    
    # Check weather file
    if weather_file:
        if os.path.exists(weather_file):
            if weather_file.endswith('.epw'):
                validation['weather_file'] = True
            else:
                validation['errors'].append("Weather file must be .epw format")
        else:
            validation['errors'].append(f"Weather file not found: {weather_file}")
    
    return validation

