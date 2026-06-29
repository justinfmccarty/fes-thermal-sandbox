#!/usr/bin/env python3
"""
Run Analysis Pipeline

Comprehensive analysis of tree stress across material scenarios.
Produces normalized percent change analysis, sensitivity analysis, plots, and report.

Usage:
    python run_analysis.py
    
Configuration:
    All configuration is loaded from config.yaml via config_locator.
    See config.yaml for available settings.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# IMPORTS - Project modules
# =============================================================================
from config_locator import get_config, get_path
from weather_loader import load_epw, find_warmest_day, get_week_around_day
from tree_species import TreeSpeciesDatabase
from grid_material_mapping import load_grid_material_mapping
from biophysical_tree_stress import BiophysicalTreeStressCalculator
from risk_metrics import calculate_stress_summary
import plot_formatting as pf
import plots
# =============================================================================
# CONFIGURATION - All values from config.yaml
# =============================================================================
_config = get_config()

# Paths from config (resolved for cross-platform compatibility)
RAYTRACING_DIR = get_path('raytracing_results_dir')
OUTPUT_DIR = get_path('analysis_results_dir')
WEATHER_FILE = get_path('weather_file')

# Scenario instructions from config
_instructions = _config.simulation.instructions
# Extract unique ratios from instructions
LANDSCAPE_RATIOS = sorted(list(set(instr[0] for instr in _instructions)))
FACADE_RATIOS = sorted(list(set(instr[1] for instr in _instructions)))


def create_output_dir():
    """Create output directory if it doesn't exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, 'plots'), exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")


def get_T_crit() -> float:
    """Get critical leaf temperature from config."""
    config = get_config()
    return config.model.risk.T_crit


def get_soil_params() -> dict:
    """Get soil parameters from config."""
    config = get_config()
    return {
        'theta_sat': config.model.soil.theta_sat,
        'theta_init': config.model.soil.theta_init,
        'Z_r': config.model.soil.Z_r,
        'k_drain_default': config.model.soil.k_drain_default
    }


def build_scenario_mapping() -> pd.DataFrame:
    """
    Build mapping from scenario_id to landscape/facade ratios.
    
    Uses actual config instructions to ensure correct mapping.
    
    Returns:
        DataFrame with columns: scenario_id, landscape_ratio, facade_ratio
    """
    scenarios = []
    for idx, instr in enumerate(_instructions):
        # Config format: [landscape_ratio, facade_ratio]
        scenarios.append({
            'scenario_id': f'scenario_{idx:03d}',
            'landscape_ratio': instr[0],
            'facade_ratio': instr[1]
        })
    return pd.DataFrame(scenarios)


# =============================================================================
# SECTION 1: BIOPHYSICAL ANALYSIS
# =============================================================================
def run_biophysical_analysis() -> Dict[str, pd.DataFrame]:
    """
    Run biophysical analysis for all scenarios.
    
    Returns:
        Dictionary mapping scenario_id -> results DataFrame
    """
    print("\n" + "="*70)
    print("SECTION 1: BIOPHYSICAL ANALYSIS")
    print("="*70)
    
    # Get config (for non-path values)
    config = get_config()
    
    # Load common resources
    print("\nLoading resources...")
    weather_data = load_epw(WEATHER_FILE)
    print(f"   Weather data: {len(weather_data)} hours")
    
    # Find warmest week
    day_of_year, _, warmest_date = find_warmest_day(WEATHER_FILE)
    start_day, end_day = get_week_around_day(day_of_year)
    warmest_week_start = start_day * 24
    warmest_week_hours = (end_day - start_day + 1) * 24
    print(f"   Warmest week: days {start_day+1}-{end_day+1} ({warmest_week_hours} hours)")
    
    # Load species database (use get_path for cross-platform compatibility)
    species_db_path = get_path('species_database_file')
    species_db = TreeSpeciesDatabase(csv_path=species_db_path)
    print(f"   Species database: {len(species_db.species_dict)} species")
    
    # Load material database
    from material_scenario_workflow import MaterialDatabase
    material_db_path = get_path('material_database_file')
    material_db = MaterialDatabase(root_material_db_path=material_db_path)
    print(f"   Material database loaded")
    
    # Load grid material mapping
    grid_material_path = get_path('scenario_grid_materials_file')
    grid_material_mapping = load_grid_material_mapping(grid_material_path)
    print(f"   Grid material mapping: {len(grid_material_mapping)} records")
    
    # Load tree points
    tree_points_path = get_path('tree_points_file')
    tree_points = pd.read_csv(tree_points_path)
    # Rename columns to match expected format
    tree_points = tree_points.rename(columns={
        'x_coord': 'xcoord',
        'y_coord': 'ycoord', 
        'z_coord': 'zcoord'
    })
    print(f"   Tree points: {len(tree_points)} trees")
    
    # Load sensor points from baseline grid (contains coordinates and grid_name for material mapping)
    sensor_points_path = get_path('sensor_points_file')
    sensor_points = pd.read_csv(sensor_points_path)
    sensor_points = sensor_points.rename(columns={
        'x_coord': 'xcoord',
        'y_coord': 'ycoord',
        'z_coord': 'zcoord'
    })
    print(f"   Sensor points: {len(sensor_points)}")
    
    # Get weather subset for warmest week
    weather_warmest = weather_data.iloc[warmest_week_start:warmest_week_start + warmest_week_hours].copy()
    weather_warmest = weather_warmest.reset_index(drop=True)
    
    # Run analysis for each scenario (excluding baseline)
    results = {}
    scenario_ids = [f'scenario_{i:03d}' for i in range(25)]
    
    for scenario_id in scenario_ids:
        print(f"\n   Processing {scenario_id}...")
        
        # Load irradiance data
        direct_path = os.path.join(RAYTRACING_DIR, f'{scenario_id}_direct.feather')
        diffuse_path = os.path.join(RAYTRACING_DIR, f'{scenario_id}_diffuse.feather')
        
        if not os.path.exists(direct_path) or not os.path.exists(diffuse_path):
            print(f"      Skipping - files not found")
            continue
        
        direct_df = pd.read_feather(direct_path)
        diffuse_df = pd.read_feather(diffuse_path)
        
        # Feather files have rows=sensors, columns=hours - need to transpose
        # So that rows=hours, columns=sensors (what the calculator expects)
        direct_df = direct_df.T
        diffuse_df = diffuse_df.T
        
        # Extract warmest week data using same indexing for all scenarios
        # (All files now store data at correct calendar positions)
        direct_df = direct_df.iloc[warmest_week_start:warmest_week_start + warmest_week_hours].copy()
        diffuse_df = diffuse_df.iloc[warmest_week_start:warmest_week_start + warmest_week_hours].copy()
        direct_df = direct_df.reset_index(drop=True)
        diffuse_df = diffuse_df.reset_index(drop=True)
        weather_for_calc = weather_warmest
        
        print(f"      Irradiance hours: {len(direct_df)}")
        
        # Create calculator
        calculator = BiophysicalTreeStressCalculator(
            tree_points=tree_points,
            sensor_points=sensor_points,
            species_db=species_db,
            material_db=material_db,
            weather_data=weather_for_calc,
            grid_material_mapping=grid_material_mapping
        )
        
        # Run simulation with config parameters
        soil_params = get_soil_params()
        results_df = calculator.simulate_hourly(
            direct_df=direct_df,
            diffuse_df=diffuse_df,
            scenario_id=scenario_id,
            analysis_period=None,  # Use all available hours
            initial_theta=soil_params['theta_init']
        )
        
        # Save results
        output_path = os.path.join(OUTPUT_DIR, f'biophysical_results_{scenario_id}.csv')
        results_df.to_csv(output_path, index=False)
        print(f"      Saved: {output_path}")
        
        results[scenario_id] = results_df
    
    return results


# =============================================================================
# SECTION 2: STRESS SUMMARIES WITH MRT AND TSURF
# =============================================================================
def calculate_extended_stress_summary(
    results_df: pd.DataFrame,
    T_crit: Optional[float] = None
) -> pd.DataFrame:
    """
    Calculate stress summary with additional MRT and Tsurf metrics.
    
    Extends the base calculate_stress_summary with thermal environment metrics.
    Focuses on leaf temperature for risk assessment.
    """
    if T_crit is None:
        T_crit = get_T_crit()
    
    # Get base stress summary (leaf temperature only)
    summary = calculate_stress_summary(results_df, T_crit)
    
    # Add MRT and Tsurf metrics per tree
    mrt_metrics = []
    tsurf_metrics = []
    
    for tree_id in results_df['tree_id'].unique():
        tree_data = results_df[results_df['tree_id'] == tree_id]
        
        mrt_metrics.append({
            'tree_id': tree_id,
            'mean_MRT_C': float(tree_data['MRT'].mean()),
            'max_MRT_C': float(tree_data['MRT'].max())
        })
        
        tsurf_metrics.append({
            'tree_id': tree_id,
            'mean_Tsurf_C': float(tree_data['Tsurf'].mean()),
            'max_Tsurf_C': float(tree_data['Tsurf'].max())
        })
    
    mrt_df = pd.DataFrame(mrt_metrics)
    tsurf_df = pd.DataFrame(tsurf_metrics)
    
    # Merge into summary
    summary = summary.merge(mrt_df, on='tree_id')
    summary = summary.merge(tsurf_df, on='tree_id')
    
    return summary


def calculate_all_stress_summaries(
    results: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    Calculate stress summaries for all scenarios.
    
    Returns:
        Master DataFrame with all scenarios and their stress metrics
    """
    print("\n" + "="*70)
    print("SECTION 2: STRESS SUMMARIES")
    print("="*70)
    
    scenario_mapping = build_scenario_mapping()
    all_summaries = []
    
    for scenario_id, results_df in results.items():
        print(f"   Calculating summary for {scenario_id}...")
        
        summary = calculate_extended_stress_summary(results_df)
        summary['scenario_id'] = scenario_id
        
        # Add landscape/facade ratios from scenario mapping
        scenario_info = scenario_mapping[scenario_mapping['scenario_id'] == scenario_id]
        if len(scenario_info) > 0:
            summary['landscape_ratio'] = scenario_info['landscape_ratio'].values[0]
            summary['facade_ratio'] = scenario_info['facade_ratio'].values[0]
        else:
            summary['landscape_ratio'] = np.nan
            summary['facade_ratio'] = np.nan
        
        all_summaries.append(summary)
    
    master_summary = pd.concat(all_summaries, ignore_index=True)
    
    # Save master summary
    output_path = os.path.join(OUTPUT_DIR, 'stress_summary_all_scenarios.csv')
    master_summary.to_csv(output_path, index=False)
    print(f"\n   Saved: {output_path}")
    
    return master_summary


# =============================================================================
# SECTION 3: NORMALIZED PERCENT CHANGE
# =============================================================================
def calculate_percent_change(master_summary: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate normalized percent change from middle scenario (50%, 50%) for all metrics.
    
    Returns:
        DataFrame with scenario-level percent changes relative to scenario_012
    """
    print("\n" + "="*70)
    print("SECTION 3: NORMALIZED PERCENT CHANGE FROM MIDDLE SCENARIO")
    print("="*70)
    
    # Get middle scenario (scenario_012: 50%, 50%) means as reference
    middle_data = master_summary[master_summary['scenario_id'] == 'scenario_012']
    middle_means = {
        'heat_stress_hours': middle_data['heat_stress_hours'].mean(),
        'degree_hours': middle_data['degree_hours'].mean(),
        'mean_Tleaf_C': middle_data['mean_Tleaf_C'].mean(),
        'max_Tleaf_C': middle_data['max_Tleaf_C'].mean(),
        'mean_MRT_C': middle_data['mean_MRT_C'].mean(),
        'max_MRT_C': middle_data['max_MRT_C'].mean(),
        'mean_Tsurf_C': middle_data['mean_Tsurf_C'].mean(),
        'max_Tsurf_C': middle_data['max_Tsurf_C'].mean()
    }
    
    print(f"\n   Middle scenario (50%, 50%) means:")
    for metric, value in middle_means.items():
        print(f"      {metric}: {value:.3f}")
    
    # Calculate scenario-level aggregates and percent change
    scenario_mapping = build_scenario_mapping()
    pct_changes = []
    
    for _, scenario in scenario_mapping.iterrows():
        sid = scenario['scenario_id']
        scenario_data = master_summary[master_summary['scenario_id'] == sid]
        
        if len(scenario_data) == 0:
            continue
        
        row = {
            'scenario_id': sid,
            'landscape_ratio': scenario['landscape_ratio'],
            'facade_ratio': scenario['facade_ratio']
        }
        
        # Calculate means and percent changes
        for metric, middle_val in middle_means.items():
            scenario_mean = scenario_data[metric].mean()
            row[f'{metric}_mean'] = scenario_mean
            
            if middle_val != 0:
                pct = (scenario_mean - middle_val) / abs(middle_val) * 100
            else:
                pct = 0.0 if scenario_mean == 0 else np.inf
            row[f'{metric}_pct_change'] = pct
        
        pct_changes.append(row)
    
    pct_df = pd.DataFrame(pct_changes)
    
    # Save
    output_path = os.path.join(OUTPUT_DIR, 'pct_change_summary.csv')
    pct_df.to_csv(output_path, index=False)
    print(f"\n   Saved: {output_path}")
    
    # Print key findings (using degree_hours as primary risk metric)
    print(f"\n   Key findings:")
    risk_col = 'degree_hours_pct_change'
    if risk_col in pct_df.columns:
        max_risk_row = pct_df.loc[pct_df[risk_col].idxmax()]
        min_risk_row = pct_df.loc[pct_df[risk_col].idxmin()]
        print(f"      Max stress increase: {max_risk_row[risk_col]:.2f}% ({max_risk_row['scenario_id']})")
        print(f"      Max stress decrease: {min_risk_row[risk_col]:.2f}% ({min_risk_row['scenario_id']})")
    
    return pct_df


# =============================================================================
# SECTION 4: SENSITIVITY ANALYSIS
# =============================================================================
def calculate_area_weighted_properties(scenario_id: str) -> Dict[str, float]:
    """
    Calculate area-weighted mean albedo and emissivity for a scenario.
    
    Computes properties for combined surfaces, as well as separate
    landscape (ground) and facade surface types.
    
    Returns:
        Dictionary with:
        - mean_albedo, mean_emissivity, total_area (combined)
        - landscape_albedo, landscape_emissivity, landscape_area
        - facade_albedo, facade_emissivity, facade_area
    """
    # Load material database
    material_db = pd.read_csv('root_material_database.csv')
    
    # Load grid materials for scenario
    grid_materials = pd.read_csv('grid_records/scenario_grid_materials.csv')
    scenario_materials = grid_materials[grid_materials['scenario_id'] == scenario_id]
    
    # Default return for empty scenario
    empty_result = {
        'mean_albedo': np.nan, 'mean_emissivity': np.nan, 'total_area': 0,
        'landscape_albedo': np.nan, 'landscape_emissivity': np.nan, 'landscape_area': 0,
        'facade_albedo': np.nan, 'facade_emissivity': np.nan, 'facade_area': 0
    }
    
    if len(scenario_materials) == 0:
        return empty_result
    
    # Join with material properties
    merged = scenario_materials.merge(
        material_db[['material_name', 'shortwave_albedo', 'thermal_emissivity']],
        on='material_name',
        how='left'
    )
    
    # Helper function for area-weighted mean
    def weighted_mean(df, col):
        area = df['area_m2'].sum()
        if area == 0:
            return np.nan
        return (df[col] * df['area_m2']).sum() / area
    
    # Calculate combined area-weighted means
    total_area = merged['area_m2'].sum()
    if total_area == 0:
        return empty_result
    
    mean_albedo = weighted_mean(merged, 'shortwave_albedo')
    mean_emissivity = weighted_mean(merged, 'thermal_emissivity')
    
    # Filter by surface type
    landscape = merged[merged['ground_or_facade'] == 'ground']
    facade = merged[merged['ground_or_facade'] == 'facade']
    
    # Calculate separate landscape and facade properties
    landscape_area = landscape['area_m2'].sum()
    facade_area = facade['area_m2'].sum()
    
    return {
        'mean_albedo': mean_albedo,
        'mean_emissivity': mean_emissivity,
        'total_area': total_area,
        'landscape_albedo': weighted_mean(landscape, 'shortwave_albedo'),
        'landscape_emissivity': weighted_mean(landscape, 'thermal_emissivity'),
        'landscape_area': landscape_area,
        'facade_albedo': weighted_mean(facade, 'shortwave_albedo'),
        'facade_emissivity': weighted_mean(facade, 'thermal_emissivity'),
        'facade_area': facade_area
    }


def run_sensitivity_analysis(pct_df: pd.DataFrame) -> pd.DataFrame:
    """
    Run sensitivity analysis: risk vs albedo and emissivity.
    
    Returns:
        DataFrame with scenario properties and regression results
    """
    print("\n" + "="*70)
    print("SECTION 4: SENSITIVITY ANALYSIS")
    print("="*70)
    
    # Calculate material properties for each scenario
    print("\n   Calculating area-weighted material properties...")
    
    rows = []
    for _, row in pct_df.iterrows():
        sid = row['scenario_id']
        props = calculate_area_weighted_properties(sid)
        
        rows.append({
            'scenario_id': sid,
            'landscape_ratio': row['landscape_ratio'],
            'facade_ratio': row['facade_ratio'],
            'mean_albedo': props['mean_albedo'],
            'mean_emissivity': props['mean_emissivity'],
            'total_area': props['total_area'],
            # Separate landscape properties
            'landscape_albedo': props['landscape_albedo'],
            'landscape_emissivity': props['landscape_emissivity'],
            'landscape_area': props['landscape_area'],
            # Separate facade properties
            'facade_albedo': props['facade_albedo'],
            'facade_emissivity': props['facade_emissivity'],
            'facade_area': props['facade_area'],
            # Risk metrics
            'degree_hours_pct_change': row.get('degree_hours_pct_change', np.nan),
            'mean_Tsurf_C_pct_change': row.get('mean_Tsurf_C_pct_change', np.nan),
            'mean_MRT_C_pct_change': row.get('mean_MRT_C_pct_change', np.nan)
        })
    
    sensitivity_df = pd.DataFrame(rows)
    
    # Linear regression: risk vs albedo
    from scipy import stats
    
    valid_data = sensitivity_df.dropna(subset=['mean_albedo', 'degree_hours_pct_change'])
    
    if len(valid_data) > 2:
        # Risk vs Albedo
        slope_a, intercept_a, r_a, p_a, se_a = stats.linregress(
            valid_data['mean_albedo'], 
            valid_data['degree_hours_pct_change']
        )
        print(f"\n   Risk vs Albedo:")
        print(f"      Slope: {slope_a:.2f} %/unit albedo")
        print(f"      R²: {r_a**2:.3f}")
        print(f"      p-value: {p_a:.4f}")
        
        # Risk vs Emissivity  
        slope_e, intercept_e, r_e, p_e, se_e = stats.linregress(
            valid_data['mean_emissivity'], 
            valid_data['degree_hours_pct_change']
        )
        print(f"\n   Risk vs Emissivity:")
        print(f"      Slope: {slope_e:.2f} %/unit emissivity")
        print(f"      R²: {r_e**2:.3f}")
        print(f"      p-value: {p_e:.4f}")
        
        # Tsurf vs Albedo
        slope_ta, intercept_ta, r_ta, p_ta, se_ta = stats.linregress(
            valid_data['mean_albedo'], 
            valid_data['mean_Tsurf_C_pct_change']
        )
        print(f"\n   Tsurf vs Albedo:")
        print(f"      Slope: {slope_ta:.2f} %/unit albedo")
        print(f"      R²: {r_ta**2:.3f}")
        print(f"      p-value: {p_ta:.4f}")
        
        # Initialize regression results dictionary
        regression_results = {
            'risk_albedo': {'slope': slope_a, 'intercept': intercept_a, 'r2': r_a**2, 'p': p_a},
            'risk_emissivity': {'slope': slope_e, 'intercept': intercept_e, 'r2': r_e**2, 'p': p_e},
            'tsurf_albedo': {'slope': slope_ta, 'intercept': intercept_ta, 'r2': r_ta**2, 'p': p_ta}
        }
        
        # Separate landscape regressions
        valid_landscape = sensitivity_df.dropna(subset=['landscape_albedo', 'degree_hours_pct_change'])
        if len(valid_landscape) > 2:
            # Risk vs Landscape Albedo
            slope, intercept, r, p, se = stats.linregress(
                valid_landscape['landscape_albedo'], 
                valid_landscape['degree_hours_pct_change']
            )
            regression_results['risk_landscape_albedo'] = {
                'slope': slope, 'intercept': intercept, 'r2': r**2, 'p': p
            }
            print(f"\n   Risk vs Landscape Albedo:")
            print(f"      Slope: {slope:.2f} %/unit albedo")
            print(f"      R²: {r**2:.3f}")
            print(f"      p-value: {p:.4f}")
            
            # Risk vs Landscape Emissivity
            slope, intercept, r, p, se = stats.linregress(
                valid_landscape['landscape_emissivity'], 
                valid_landscape['degree_hours_pct_change']
            )
            regression_results['risk_landscape_emissivity'] = {
                'slope': slope, 'intercept': intercept, 'r2': r**2, 'p': p
            }
            print(f"\n   Risk vs Landscape Emissivity:")
            print(f"      Slope: {slope:.2f} %/unit emissivity")
            print(f"      R²: {r**2:.3f}")
            print(f"      p-value: {p:.4f}")
        
        # Separate facade regressions
        valid_facade = sensitivity_df.dropna(subset=['facade_albedo', 'degree_hours_pct_change'])
        if len(valid_facade) > 2:
            # Risk vs Facade Albedo
            slope, intercept, r, p, se = stats.linregress(
                valid_facade['facade_albedo'], 
                valid_facade['degree_hours_pct_change']
            )
            regression_results['risk_facade_albedo'] = {
                'slope': slope, 'intercept': intercept, 'r2': r**2, 'p': p
            }
            print(f"\n   Risk vs Facade Albedo:")
            print(f"      Slope: {slope:.2f} %/unit albedo")
            print(f"      R²: {r**2:.3f}")
            print(f"      p-value: {p:.4f}")
            
            # Risk vs Facade Emissivity
            slope, intercept, r, p, se = stats.linregress(
                valid_facade['facade_emissivity'], 
                valid_facade['degree_hours_pct_change']
            )
            regression_results['risk_facade_emissivity'] = {
                'slope': slope, 'intercept': intercept, 'r2': r**2, 'p': p
            }
            print(f"\n   Risk vs Facade Emissivity:")
            print(f"      Slope: {slope:.2f} %/unit emissivity")
            print(f"      R²: {r**2:.3f}")
            print(f"      p-value: {p:.4f}")
        
        # Store all regression results
        sensitivity_df.attrs['regression'] = regression_results
    
    # Save
    output_path = os.path.join(OUTPUT_DIR, 'sensitivity_analysis.csv')
    sensitivity_df.to_csv(output_path, index=False)
    print(f"\n   Saved: {output_path}")
    
    return sensitivity_df


# =============================================================================
# SECTION 5: PLOT GENERATION
# =============================================================================
def generate_plots(pct_df: pd.DataFrame, sensitivity_df: pd.DataFrame, master_summary: pd.DataFrame,
                   results: Optional[Dict[str, pd.DataFrame]] = None):
    """Generate publication-quality plots.
    
    Args:
        pct_df: Percent change summary DataFrame
        sensitivity_df: Sensitivity analysis DataFrame
        master_summary: Master summary DataFrame
        results: Optional dictionary of biophysical results by scenario_id
                 (required for leaf temperature uncertainty plot)
    """
    print("\n" + "="*70)
    print("SECTION 5: PLOT GENERATION")
    print("="*70)
    
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    
    # Set style
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams['font.family'] = 'serif'
    plt.rcParams['font.size'] = 11
    plt.rcParams['axes.labelsize'] = 12
    plt.rcParams['axes.titlesize'] = 14
    
    plots_dir = os.path.join(OUTPUT_DIR, 'plots')
    
    # --- PLOT 1: Heatmap of risk percent change ---
    print("\n   Generating heatmap...")
    fig = plots.plot_risk_heatmap(
        pct_df,
        output_path=os.path.join(plots_dir, 'pct_change_heatmap.png')
    )
    plt.close(fig)
    
    # --- PLOT 1b: Scenario concept diagram ---
    print("   Generating scenario concept diagram...")
    fig = plots.plot_scenario_concept(
        sensitivity_df,
        output_path=os.path.join(plots_dir, 'scenario_concept_diagram.png')
    )
    plt.close(fig)
    
    # --- PLOT 1c: Material properties comparison ---
    print("   Generating material properties comparison...")
    material_db_path = get_path('material_database_file')
    fig = plots.plot_material_properties_comparison(
        material_db_path=material_db_path,
        output_path=os.path.join(plots_dir, 'material_properties_comparison.png')
    )
    plt.close(fig)
    
    # --- PLOT 2: Sensitivity curves (combined) ---
    print("   Generating sensitivity curves (combined)...")
    fig = plots.plot_combined_sensitivity(
        sensitivity_df,
        output_path=os.path.join(plots_dir, 'sensitivity_curves.png')
    )
    plt.close(fig)
    
    # --- PLOT 2b: Sensitivity curves by surface type ---
    print("   Generating sensitivity curves by surface type...")
    fig = plots.plot_sensitivity_by_surface_type(
        sensitivity_df,
        output_path=os.path.join(plots_dir, 'sensitivity_by_surface_type.png')
    )
    plt.close(fig)
    
    # --- PLOT 3: Box plot comparison ---
    print("   Generating box plot...")
    
    # Select key scenarios for comparison (excluding baseline)
    key_scenarios = ['scenario_000', 'scenario_012', 'scenario_024']
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    box_data = []
    labels = []
    for sid in key_scenarios:
        if sid in master_summary['scenario_id'].values:
            data = master_summary[master_summary['scenario_id'] == sid]['degree_hours']
            box_data.append(data.values)
            if sid == 'scenario_000':
                labels.append('S000\n(0%, 0%)')
            elif sid == 'scenario_012':
                labels.append('S012 - Middle\n(50%, 50%)')
            elif sid == 'scenario_024':
                labels.append('S024\n(100%, 100%)')
    
    bp = ax.boxplot(box_data, labels=labels, patch_artist=True)
    
    colors = ['#FFB3B3', '#FFFFB3', '#B3FFB3']
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
    
    ax.set_ylabel('Weighted Risk Index')
    ax.set_xlabel('Scenario (Landscape %, Facade %)')
    ax.set_title('Distribution of Tree Risk Index by Scenario')
    
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, 'scenario_comparison_boxplot.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # --- PLOT 4: Top/Bottom scenarios bar chart ---
    print("   Generating bar chart...")
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Sort by risk change
    sorted_df = pct_df.sort_values('degree_hours_pct_change')
    
    # Get top 5 (lowest risk) and bottom 5 (highest risk)
    top5 = sorted_df.head(5)
    bottom5 = sorted_df.tail(5)
    plot_df = pd.concat([top5, bottom5])
    
    colors = ['#2ecc71' if x < 0 else '#e74c3c' for x in plot_df['degree_hours_pct_change']]
    
    bars = ax.barh(range(len(plot_df)), plot_df['degree_hours_pct_change'], color=colors)
    ax.set_yticks(range(len(plot_df)))
    ax.set_yticklabels([f"{row['scenario_id']}\n({row['landscape_ratio']:.0%}, {row['facade_ratio']:.0%})" 
                        for _, row in plot_df.iterrows()])
    ax.axvline(x=0, color='black', linewidth=0.5)
    ax.set_xlabel('% Change in Weighted Risk Index')
    ax.set_title('Top 5 Best and Worst Scenarios for Tree Risk (vs Middle 50%/50%)')
    
    # Add value labels
    for i, (idx, row) in enumerate(plot_df.iterrows()):
        val = row['degree_hours_pct_change']
        ax.text(val + (0.5 if val >= 0 else -0.5), i, f'{val:.1f}%', 
                va='center', ha='left' if val >= 0 else 'right', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, 'top_scenarios_bar.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # --- PLOT 5: MRT and Tsurf heatmaps ---
    print("   Generating MRT/Tsurf heatmaps...")
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    for ax, metric, title in zip(
        axes, 
        ['mean_MRT_C_pct_change', 'mean_Tsurf_C_pct_change'],
        ['Mean Radiant Temperature (MRT)', 'Surface Temperature (Tsurf)']
    ):
        pivot = pct_df.pivot(
            index='facade_ratio',
            columns='landscape_ratio',
            values=metric
        )
        
        vmax = max(abs(pivot.min().min()), abs(pivot.max().max()))
        vmin = -vmax
        
        im = ax.imshow(pivot.values, cmap='RdYlBu_r', vmin=vmin, vmax=vmax, aspect='equal')
        plt.colorbar(im, ax=ax, label='% Change')
        
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                val = pivot.values[i, j]
                color = 'white' if abs(val) > vmax*0.5 else 'black'
                ax.text(j, i, f'{val:.1f}%', ha='center', va='center', color=color, fontsize=9)
        
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels([f'{x:.0%}' for x in pivot.columns])
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([f'{y:.0%}' for y in pivot.index])
        ax.set_xlabel('Landscape Vegetation Ratio')
        ax.set_ylabel('Facade Vegetation Ratio')
        ax.set_title(f'% Change in {title} (vs Middle 50%/50%)')
    
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, 'mrt_tsurf_heatmaps.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # --- PLOT 6: Leaf temperature uncertainty plot ---
    if results is not None and len(results) > 0:
        print("   Generating leaf temperature uncertainty plot...")
        
        # Build leaf temperature DataFrame from results
        # Use a single tree's data across all scenarios to show variability
        first_scenario = list(results.keys())[0]
        first_result = results[first_scenario]
        
        # Get unique hours from the first scenario
        if 'hour' in first_result.columns:
            hours = first_result['hour'].unique()
        else:
            hours = range(len(first_result[first_result['tree_id'] == first_result['tree_id'].iloc[0]]))
        
        # Create datetime index for plotting
        # Use the analysis period (warmest week)
        day_of_year, _, _ = find_warmest_day(WEATHER_FILE)
        start_day, end_day = get_week_around_day(day_of_year)
        warmest_week_start = start_day * 24
        warmest_week_hours = (end_day - start_day + 1) * 24
        
        # Load weather data for the warmest week
        weather_data = load_epw(WEATHER_FILE)
        weather_subset = weather_data.iloc[warmest_week_start:warmest_week_start + warmest_week_hours].reset_index(drop=True)
        
        # Create time index
        start_date = pd.Timestamp('2024-01-01') + pd.Timedelta(days=start_day)
        time_index = pd.date_range(start=start_date, periods=warmest_week_hours, freq='h')
        
        # Build DataFrame with mean leaf temp per scenario per hour
        leaf_temp_data = {}
        for scenario_id, result_df in results.items():
            # Average across all trees for each hour
            hourly_mean = result_df.groupby('hour')['T_leaf'].mean()
            if len(hourly_mean) == len(time_index):
                leaf_temp_data[scenario_id] = hourly_mean.values
        
        if leaf_temp_data:
            leaf_temp_df = pd.DataFrame(leaf_temp_data, index=time_index)
            
            # Rename weather columns to match expected format
            weather_plot = weather_subset.copy()
            weather_plot['Ta'] = weather_plot['T_air'] if 'T_air' in weather_plot.columns else weather_plot.get('Ta', 20)
            weather_plot['K_down'] = weather_plot['K_down'] if 'K_down' in weather_plot.columns else weather_plot.get('GHI', 0)
            
            fig = plots.plot_leaf_temp_uncertainty(
                leaf_temp_df,
                weather_plot,
                output_path=os.path.join(plots_dir, 'leaf_temp_uncertainty.png')
            )
            plt.close(fig)
    
    print(f"\n   All plots saved to: {plots_dir}/")


# =============================================================================
# SECTION 6: REPORT GENERATION
# =============================================================================
def generate_report(pct_df: pd.DataFrame, sensitivity_df: pd.DataFrame, master_summary: pd.DataFrame):
    """Generate markdown report with key findings."""
    print("\n" + "="*70)
    print("SECTION 6: REPORT GENERATION")
    print("="*70)
    
    report_lines = []
    report_lines.append("# Tree Stress Analysis Report")
    report_lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"\nData source: `{RAYTRACING_DIR}`")
    
    # Summary statistics
    report_lines.append("\n## Summary Statistics\n")
    report_lines.append(f"- Total scenarios analyzed: {len(pct_df)}")
    report_lines.append(f"- Total trees per scenario: {master_summary.groupby('scenario_id').size().iloc[0]}")
    report_lines.append(f"- Reference scenario: scenario_012 (50% landscape, 50% facade)")
    
    # Middle scenario characteristics (reference point)
    middle = master_summary[master_summary['scenario_id'] == 'scenario_012']
    report_lines.append("\n### Middle Scenario (50%, 50%) - Reference Conditions\n")
    report_lines.append(f"- Mean T_leaf: {middle['mean_Tleaf_C'].mean():.2f}°C")
    report_lines.append(f"- Mean MRT: {middle['mean_MRT_C'].mean():.2f}°C")
    report_lines.append(f"- Mean Tsurf: {middle['mean_Tsurf_C'].mean():.2f}°C")
    report_lines.append(f"- Mean Degree Hours: {middle['degree_hours'].mean():.2f}")
    
    # Key findings
    report_lines.append("\n## Key Findings\n")
    
    # Risk changes
    risk_col = 'degree_hours_pct_change'
    min_row = pct_df.loc[pct_df[risk_col].idxmin()]
    max_row = pct_df.loc[pct_df[risk_col].idxmax()]
    
    report_lines.append("### Risk Index Changes (Relative to Middle Scenario)\n")
    report_lines.append(f"- **Best scenario** (lowest risk vs middle): {min_row['scenario_id']} (Landscape: {min_row['landscape_ratio']:.0%}, Facade: {min_row['facade_ratio']:.0%})")
    report_lines.append(f"  - Risk change: {min_row[risk_col]:.2f}%")
    report_lines.append(f"- **Worst scenario** (highest risk vs middle): {max_row['scenario_id']} (Landscape: {max_row['landscape_ratio']:.0%}, Facade: {max_row['facade_ratio']:.0%})")
    report_lines.append(f"  - Risk change: {max_row[risk_col]:.2f}%")
    
    # Sensitivity analysis
    report_lines.append("\n### Sensitivity Analysis\n")
    
    if 'regression' in sensitivity_df.attrs:
        reg = sensitivity_df.attrs['regression']
        
        report_lines.append("**Risk vs Albedo:**")
        report_lines.append(f"- Slope: {reg['risk_albedo']['slope']:.2f} %/unit")
        report_lines.append(f"- R²: {reg['risk_albedo']['r2']:.3f}")
        report_lines.append(f"- p-value: {reg['risk_albedo']['p']:.4f}")
        
        report_lines.append("\n**Risk vs Emissivity:**")
        report_lines.append(f"- Slope: {reg['risk_emissivity']['slope']:.2f} %/unit")
        report_lines.append(f"- R²: {reg['risk_emissivity']['r2']:.3f}")
        report_lines.append(f"- p-value: {reg['risk_emissivity']['p']:.4f}")
        
        report_lines.append("\n**Tsurf vs Albedo:**")
        report_lines.append(f"- Slope: {reg['tsurf_albedo']['slope']:.2f} %/unit")
        report_lines.append(f"- R²: {reg['tsurf_albedo']['r2']:.3f}")
        report_lines.append(f"- p-value: {reg['tsurf_albedo']['p']:.4f}")
    
    # Recommendations
    report_lines.append("\n## Recommendations\n")
    
    # Determine recommendation based on findings (relative to middle scenario)
    report_lines.append("Based on comparison to the middle scenario (50%/50%):")
    
    if min_row[risk_col] < 0:
        report_lines.append(f"1. **Some scenarios reduce tree stress below the middle scenario**. The best scenario ({min_row['scenario_id']}) shows a {abs(min_row[risk_col]):.1f}% reduction.")
    else:
        report_lines.append(f"1. **No scenarios reduce tree stress below the middle scenario**. The minimum increase is {min_row[risk_col]:.1f}%.")
    
    if max_row[risk_col] > 0:
        report_lines.append(f"2. **Some scenarios increase tree stress above the middle scenario**. The worst scenario ({max_row['scenario_id']}) shows a {abs(max_row[risk_col]):.1f}% increase.")
    
    # Check if landscape or facade has more impact
    lr_effect = pct_df.groupby('landscape_ratio')[risk_col].mean()
    fr_effect = pct_df.groupby('facade_ratio')[risk_col].mean()
    lr_range = lr_effect.max() - lr_effect.min()
    fr_range = fr_effect.max() - fr_effect.min()
    
    if lr_range > fr_range:
        report_lines.append(f"3. **Landscape vegetation has a stronger effect** than facade vegetation on tree stress (range: {lr_range:.1f}% vs {fr_range:.1f}%).")
    else:
        report_lines.append(f"3. **Facade vegetation has a stronger effect** than landscape vegetation on tree stress (range: {fr_range:.1f}% vs {lr_range:.1f}%).")
    
    # Outputs
    report_lines.append("\n## Output Files\n")
    report_lines.append(f"- `{OUTPUT_DIR}/stress_summary_all_scenarios.csv` - Per-tree stress metrics for all scenarios")
    report_lines.append(f"- `{OUTPUT_DIR}/pct_change_summary.csv` - Scenario-level percent changes from middle scenario (50%/50%)")
    report_lines.append(f"- `{OUTPUT_DIR}/sensitivity_analysis.csv` - Material properties and regression results")
    report_lines.append(f"- `{OUTPUT_DIR}/plots/` - Publication-quality figures")
    report_lines.append(f"\n**Note**: Baseline scenario is not included in this analysis. All comparisons are relative to scenario_012 (50% landscape, 50% facade).")
    
    # Write report
    report_text = '\n'.join(report_lines)
    output_path = os.path.join(OUTPUT_DIR, 'analysis_report.md')
    with open(output_path, 'w') as f:
        f.write(report_text)
    
    print(f"\n   Report saved: {output_path}")
    print("\n" + "="*70)
    print("REPORT PREVIEW")
    print("="*70)
    print(report_text)


# =============================================================================
# MAIN EXECUTION
# =============================================================================
def main():
    """Run complete analysis pipeline."""
    print("\n" + "="*70)
    print("TREE STRESS ANALYSIS PIPELINE")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"   Raytracing data: {RAYTRACING_DIR}")
    print(f"   Output directory: {OUTPUT_DIR}")
    print(f"   Weather file: {WEATHER_FILE}")
    
    # Create output directory
    create_output_dir()
    
    # Section 1: Biophysical analysis
    results = run_biophysical_analysis()
    
    # Section 2: Stress summaries
    master_summary = calculate_all_stress_summaries(results)
    
    # Section 3: Percent change
    pct_df = calculate_percent_change(master_summary)
    
    # Section 4: Sensitivity analysis
    sensitivity_df = run_sensitivity_analysis(pct_df)
    
    # Section 5: Plots (pass results for leaf temp uncertainty plot)
    generate_plots(pct_df, sensitivity_df, master_summary, results=results)
    
    # Section 6: Report
    generate_report(pct_df, sensitivity_df, master_summary)
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print(f"\nAll outputs saved to: {OUTPUT_DIR}/")
    print("\nTo re-run with new raytracing data:")
    print("   1. Change RAYTRACING_DIR at top of script")
    print("   2. Optionally change OUTPUT_DIR to keep old results")
    print("   3. Run: python run_analysis.py")


if __name__ == "__main__":
    main()
