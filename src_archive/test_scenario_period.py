"""
Test script for scenario simulation with warmest week period.
This tests a single scenario to verify the simulation period feature works.
"""
import os
import sys
from material_scenario_workflow import MaterialScenarioWorkflow

# Setup paths
if sys.platform == "win32":
    user_folder = r"c:\\Users\\Justin"
else:
    user_folder = '/Users/jmccarty'

PROJECT_ROOT = os.path.join(user_folder, 'Nextcloud', 'Projects', '35_UHI_Trees_Manitoba')
JODLA_DIR = os.path.join(PROJECT_ROOT, '00_data_code', 'jodla_project')

# Initialize workflow with warmest week period
print("="*70)
print("TESTING SCENARIO SIMULATION WITH WARMEST WEEK PERIOD")
print("="*70)

workflow = MaterialScenarioWorkflow(
    baseline_project_dir=os.path.join(JODLA_DIR, 'python', 'baseline_radiance_project'),
    scenario_project_dir=os.path.join(JODLA_DIR, 'python', 'scenario_radiance_project'),
    tree_points_file=os.path.join(JODLA_DIR, 'grid_records', 'baseline_trees.csv'),
    sensor_points_file=None,
    weather_file=os.path.join(JODLA_DIR, 'weather.epw'),
    scenario_instructions=[(0.0, 0.0)],  # Just test one scenario: all concrete
    baseline_period='annual',
    scenario_period='warmest_week'
)

print(f"\nBaseline period: {workflow.baseline_period}")
print(f"Scenario period: {workflow.scenario_period}")
print(f"Weather file: {workflow.weather_file}")

# Run just one scenario
print("\n" + "="*70)
print("Running test scenario: (0.0, 0.0) - all concrete")
print("="*70)

result = workflow.run_scenario_raytracing(
    instruction=(0.0, 0.0),
    scenario_id='test_scenario_000',
    n_workers=6,
    use_accelerad=False
)

print("\n✅ Test complete!")
if result:
    print(f"   Feather files saved to: {result}")

