# Test in a notebook or Python script
import pandas as pd
from grid_material_mapping import load_grid_material_mapping
from tree_species import TreeSpeciesDatabase
import os
import sys
from material_scenario_workflow import MaterialScenarioWorkflow
import numpy as np
import sys

# =============================================================================
# CONTROL FLAGS - Set these to control what runs
# =============================================================================
RUN_BASELINE = True      # Set to False to skip baseline if already exists
RUN_SCENARIOS = True     # Set to False to skip scenarios
FORCE_REGENERATE_BASELINE = False  # Set to True to regenerate even if exists
FORCE_REGENERATE_SCENARIOS = True # Set to True to regenerate all scenarios

if sys.platform=="win32":
    windows=True
    use_accelerad=True
    user_folder = r"c:\\Users\\Justin"
else:
    windows=False
    use_accelerad=False  # Accelerad not installed on macOS
    user_folder = '/Users/jmccarty'

# Phase 1
print("="*20+"\nPhase 1\n"+"="*20)
# Test baseline_materials.csv
baseline = pd.read_csv('grid_records/baseline_materials.csv')
print(f"Loaded {len(baseline)} material records")
print(f"Ground surfaces: {(baseline['ground_or_facade'] == 'ground').sum()}")
print(f"Facade surfaces: {(baseline['ground_or_facade'] == 'facade').sum()}")

# Test tree species database
species_db = TreeSpeciesDatabase()
species_db.load_from_csv('tree_species_database.csv')
print(f"Loaded {len(species_db.species_dict)} species")

# Phase 2
print("="*20+"\nPhase 2\n"+"="*20)
# Configure paths
PROJECT_ROOT = os.path.join(user_folder, 'Nextcloud','Projects','35_UHI_Trees_Manitoba')
JODLA_DIR = os.path.join(PROJECT_ROOT, '00_data_code', 'jodla_project')

# Create the 25 scenarios
predefined_scenarios = []
for x in np.arange(0,1.1,0.25):
    for y in np.arange(0,1.1,0.25):
        predefined_scenarios.append((x,y))

# Initialize workflow
# Note: root_material_database.csv, base_material_library.txt, and tree_species_database.csv
# are automatically loaded from the jodla_project directory
workflow = MaterialScenarioWorkflow(
    baseline_project_dir=os.path.join(JODLA_DIR, 'python','baseline_radiance_project'),
    scenario_project_dir=os.path.join(JODLA_DIR, 'python','scenario_radiance_project'),
    tree_points_file=os.path.join(JODLA_DIR, 'grid_records','baseline_trees.csv'),
    sensor_points_file=None,  # Will extract from feather columns
    weather_file=os.path.join(JODLA_DIR, 'weather.epw'),
    scenario_instructions=predefined_scenarios,
    baseline_period='annual',  # Full year for baseline
    scenario_period='warmest_week'  # Just warmest week for scenarios (much faster!)
)

# =============================================================================
# BASELINE RAYTRACING
# =============================================================================
baseline_direct_path = os.path.join(workflow.raytracing_results_dir, 'baseline_direct.feather')
baseline_diffuse_path = os.path.join(workflow.raytracing_results_dir, 'baseline_diffuse.feather')
baseline_exists = os.path.exists(baseline_direct_path) and os.path.exists(baseline_diffuse_path)

if RUN_BASELINE:
    if baseline_exists and not FORCE_REGENERATE_BASELINE:
        print("\n" + "="*70)
        print("BASELINE RAYTRACING - SKIPPING (files already exist)")
        print("="*70)
        print(f"   ✓ Found: {baseline_direct_path}")
        print(f"   ✓ Found: {baseline_diffuse_path}")
        print("   To regenerate, set FORCE_REGENERATE_BASELINE=True")
        baseline_direct, baseline_diffuse = baseline_direct_path, baseline_diffuse_path
    else:
        print("\n" + "="*70)
        print("BASELINE RAYTRACING")
        print("="*70)
        print(f"   Project: {workflow.baseline_project_dir}")
        print(f"   Output: {workflow.raytracing_results_dir}")
        if FORCE_REGENERATE_BASELINE:
            print("   Mode: FORCE REGENERATE")
        
        # Run baseline raytracing
        baseline_direct, baseline_diffuse = workflow.run_baseline_raytracing(
            n_workers=6,
            use_accelerad=use_accelerad,
            force_regenerate=FORCE_REGENERATE_BASELINE
        )
        
        print("\n✅ Baseline raytracing complete!")
        print(f"   Direct irradiance saved to: {baseline_direct}")
        print(f"   Diffuse irradiance saved to: {baseline_diffuse}")
else:
    print("\n⏭️  BASELINE RAYTRACING - SKIPPED (RUN_BASELINE=False)")
    if baseline_exists:
        print(f"   Existing files will be used:")
        print(f"   ✓ {baseline_direct_path}")
        print(f"   ✓ {baseline_diffuse_path}")

# =============================================================================
# SCENARIO RAYTRACING
# =============================================================================
if RUN_SCENARIOS:
    # Check which scenarios already exist
    existing_scenarios = []
    missing_scenarios = []
    
    for i, instruction in enumerate(predefined_scenarios):
        scenario_id = f"scenario_{i:03d}"
        direct_path = os.path.join(workflow.raytracing_results_dir, f'{scenario_id}_direct.feather')
        diffuse_path = os.path.join(workflow.raytracing_results_dir, f'{scenario_id}_diffuse.feather')
        
        if os.path.exists(direct_path) and os.path.exists(diffuse_path):
            existing_scenarios.append(scenario_id)
        else:
            missing_scenarios.append(scenario_id)
    
    print("\n" + "="*70)
    print("SCENARIO RAYTRACING")
    print("="*70)
    print(f"   Total scenarios: {len(predefined_scenarios)}")
    print(f"   ✓ Already completed: {len(existing_scenarios)}")
    print(f"   ⏳ To run: {len(missing_scenarios)}")
    print(f"   Simulation period: {workflow.scenario_period}")
    
    if FORCE_REGENERATE_SCENARIOS:
        print("   Mode: FORCE REGENERATE ALL")
    elif len(missing_scenarios) == 0:
        print("\n✅ All scenarios already complete! Nothing to do.")
        print("   To regenerate, set FORCE_REGENERATE_SCENARIOS=True")
    
    if FORCE_REGENERATE_SCENARIOS or len(missing_scenarios) > 0:
        print("\n🚀 Running scenarios...")
        print(f"   Mode: {FORCE_REGENERATE_SCENARIOS}")
        print(f"   Accelerad: {use_accelerad}")
        
        scenario_results = workflow.run_raytracing_phase(
            n_workers=6,
            use_accelerad=use_accelerad,
            force_regenerate=FORCE_REGENERATE_SCENARIOS
        )
        
        print("\n✅ Scenario raytracing complete!")
        print(f"   Results saved to: {workflow.raytracing_results_dir}")
else:
    print("\n⏭️  SCENARIO RAYTRACING - SKIPPED (RUN_SCENARIOS=False)")