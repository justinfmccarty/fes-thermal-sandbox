import os
import pickle
from material_scenario_workflow import MaterialScenarioWorkflow
import glob
import sys
import numpy as np
from utils import reconstruct_scenario_feather_files
import random 
# random.seed(42)  # REMOVED: causes all scenarios to select same surfaces

if sys.platform=="win32":
    windows=True
    use_accelerad=True
    user_folder = r"c:\\Users\\Justin"
else:
    windows=False
    use_accelerad=False  # Accelerad not installed on macOS
    user_folder = '/Users/jmccarty'

PROJECT_ROOT = os.path.join(user_folder, 'Nextcloud','Projects','35_UHI_Trees_Manitoba')
JODLA_DIR = os.path.join(PROJECT_ROOT, '00_data_code', 'jodla_project')


# Create the 25 scenarios
predefined_scenarios = []
for x in np.arange(0,1.1,0.25):
    for y in np.arange(0,1.1,0.25):
        predefined_scenarios.append((x,y))
        
        
workflow = MaterialScenarioWorkflow(
    baseline_project_dir=os.path.join(JODLA_DIR, 'python','baseline_radiance_project'),
    scenario_project_dir=os.path.join(JODLA_DIR, 'python','scenario_radiance_project'),
    tree_points_file=os.path.join(JODLA_DIR, 'grid_records','baseline_trees.csv'),
    sensor_points_file=os.path.join(JODLA_DIR, 'grid_records','jodla_scenario_grid.csv'),  # Fixed: 17,399 sensors matching feather files
    weather_file=os.path.join(JODLA_DIR, 'weather.epw'),
    scenario_instructions=predefined_scenarios,
    baseline_period='annual',  # Full year for baseline
    scenario_period='warmest_week'  # Just warmest week for scenarios (much faster!)
)

scenario_feather_files = reconstruct_scenario_feather_files(workflow.raytracing_results_dir)

# for debug
my_dict = {}

debug_list =  random.sample(list(scenario_feather_files.keys()), 10)

debug_list = ['scenario_020', 'scenario_008']
for key in debug_list:
    my_dict[key] = scenario_feather_files[key]

# Phase 2: Analyze tree risk from feather files
results = workflow.run_tree_risk_analysis_phase(
    analysis_period=None,  # None = analyze all available data in each dataset
                           # (baseline=full year, scenarios=warmest week)
    scenario_feather_files=scenario_feather_files
)


# Save results
output_dir = os.path.join(JODLA_DIR, 'outputs')
os.makedirs(output_dir, exist_ok=True)

# Save as pickle file
results_file = os.path.join(output_dir, 'scenario_analysis_results.pkl')
with open(results_file, 'wb') as f:
    pickle.dump(results, f)

print(f"\n✅ Results saved to: {results_file}")
print("\nResults dictionary structure:")
print(f"   Keys: {list(results.keys())[:5]}...")  # Show first 5 scenario IDs
print(f"   Total scenarios: {len(results)}")

# Example: access a specific scenario's results
if len(results) > 0:
    example_scenario = list(results.keys())[0]
    example_result = results[example_scenario]
    print(f"\nExample result for {example_scenario}:")
    if isinstance(example_result, dict):
        print(f"   Result keys: {list(example_result.keys())}")
    else:
        print(f"   Result type: {type(example_result)}")