"""
Example usage of the Material Scenario Workflow

This script demonstrates how to use the workflow to analyze material scenarios
and their impact on tree heat stress.
"""

import os
import sys
from material_scenario_workflow import MaterialScenarioWorkflow
from utils import save_results, validate_inputs

# Project paths
PROJECT_ROOT = '/Users/jmccarty/Nextcloud/Projects/35_UHI_Trees_Manitoba'

# Radiance project configuration
# Baseline is immutable and used for reference
BASELINE_PROJECT_DIR = os.path.join(
    PROJECT_ROOT,
    '00_data_code/jodla_project/baseline_radiance_project'
)
# Scenario project has optimized grid files for faster simulation
SCENARIO_PROJECT_DIR = os.path.join(
    PROJECT_ROOT,
    '00_data_code/jodla_project/scenario_radiance_project'
)
RADIANCE_SURFACE_KEY = ''  # Empty because model/ is already in project_dir

# Input files
BASELINE_FEATHER_FILE = None  # Set if you have a baseline feather file
TREE_POINTS_FILE = os.path.join(
    PROJECT_ROOT,
    '00_data_code/20251222_ROI_chosen_points.csv'  # Tree points with xcoord, ycoord, zcoord, number
)
SENSOR_POINTS_FILE = os.path.join(
    PROJECT_ROOT,
    '01_models/jodla_baseline_grid_record.csv'  # Sensor points with x_coord, y_coord, z_coord
)
WEATHER_FILE = os.path.join(
    PROJECT_ROOT,
    '01_models/weather.epw'
)

def main():
    """Run the material scenario workflow."""
    
    # Validate inputs
    print("Validating inputs...")
    validation = validate_inputs(
        radiance_project_dir=BASELINE_PROJECT_DIR,
        tree_points_file=TREE_POINTS_FILE,
        sensor_points_file=SENSOR_POINTS_FILE,
        weather_file=WEATHER_FILE
    )
    
    # Check if scenario project exists
    if not os.path.exists(SCENARIO_PROJECT_DIR):
        print(f"\n⚠ Warning: Scenario project directory not found: {SCENARIO_PROJECT_DIR}")
        print("   Will use baseline project for scenarios (slower but will work)")
        scenario_project_dir = None
    else:
        scenario_project_dir = SCENARIO_PROJECT_DIR
        print(f"✓ Using scenario project: {scenario_project_dir}")
    
    if validation['errors']:
        print("\nValidation errors found:")
        for error in validation['errors']:
            print(f"  - {error}")
        return None
    
    print("✓ All inputs validated successfully\n")
    
    # Define scenario instructions (optional)
    # Each tuple is (landscape_naturalness, facade_naturalness) from 0.0 to 1.0
    # If None, random scenarios will be generated
    predefined_scenarios = [
        (0.0, 0.0),   # All concrete
        (1.0, 0.0),   # Green landscape, concrete facades
        (0.0, 1.0),   # Concrete landscape, green facades
        (1.0, 1.0),   # All green
        (0.5, 0.5),   # 50/50 mix
    ]
    
    # Initialize workflow
    workflow = MaterialScenarioWorkflow(
        baseline_project_dir=BASELINE_PROJECT_DIR,
        scenario_project_dir=scenario_project_dir,  # Uses optimized grid files
        radiance_surface_key=RADIANCE_SURFACE_KEY,
        baseline_feather_file=BASELINE_FEATHER_FILE,
        tree_points_file=TREE_POINTS_FILE,
        sensor_points_file=SENSOR_POINTS_FILE,
        weather_file=WEATHER_FILE,
        scenario_instructions=predefined_scenarios  # Use predefined or None for random
    )
    
    # Option 1: Run full workflow (raytracing + analysis)
    # results = workflow.run_full_workflow(
    #     n_scenarios=5,  # Start with small number for testing
    #     analysis_period=None,  # Will auto-detect warmest July day
    #     n_workers=6,
    #     use_accelerad=False  # Set to True if Accelerad is installed
    # )
    
    # Option 2: Run phases separately
    # Phase 1: Generate feather files
    # Set use_accelerad=True to use GPU-accelerated Accelerad (faster)
    scenario_feather_files = workflow.run_raytracing_phase(
        n_scenarios=5,  # Start with small number for testing
        n_workers=6,
        use_accelerad=False  # Set to True if Accelerad is installed
    )
    
    # Phase 2: Analyze tree risk from feather files
    results = workflow.run_tree_risk_analysis_phase(
        analysis_period=None,  # Will auto-detect warmest July day
        scenario_feather_files=scenario_feather_files
    )
    
    # Save results
    output_dir = os.path.join(PROJECT_ROOT, '00_data_code/jodla_project/outputs')
    save_results(results, output_dir, prefix='scenario')
    
    return results

if __name__ == "__main__":
    results = main()

