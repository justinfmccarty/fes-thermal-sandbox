#!/usr/bin/env python3
"""
Verify that materials are actually being changed differently for each scenario.
This script will:
1. Run scenario_000 and scenario_024
2. Keep temp directories (don't cleanup)
3. Compare the material assignments in envelope.rad files
4. Show which surfaces were changed and how
"""

import os
import sys
import shutil
from material_scenario_workflow import MaterialScenarioWorkflow
from config_locator import get_config, get_path

# Configuration from config.yaml (cross-platform)
config = get_config()
use_accelerad = config.simulation.use_accelerad
JODLA_DIR = get_path('project_root')

# Test scenarios
test_scenarios = [
    ((0.0, 0.0), 'scenario_000'),  # All concrete (least natural)
    ((1.0, 1.0), 'scenario_024')   # All vegetation (most natural)
]

print("="*70)
print("MATERIAL CHANGE VERIFICATION")
print("="*70)
print("This will verify that different scenarios get different material assignments")
print("="*70)

# Create a persistent temp directory for inspection
temp_inspect_dir = os.path.join(JODLA_DIR, 'temp_material_inspection')
if os.path.exists(temp_inspect_dir):
    shutil.rmtree(temp_inspect_dir)
os.makedirs(temp_inspect_dir, exist_ok=True)

# Initialize workflow
workflow = MaterialScenarioWorkflow(
    baseline_project_dir=os.path.join(JODLA_DIR, 'python_debug', 'baseline_radiance_project'),
    scenario_project_dir=os.path.join(JODLA_DIR, 'python_debug', 'scenario_radiance_project'),
    tree_points_file=os.path.join(JODLA_DIR, 'grid_records', 'baseline_trees.csv'),
    sensor_points_file=os.path.join(JODLA_DIR, 'grid_records', 'debug_jodla_scenario_grid.csv'),
    weather_file=os.path.join(JODLA_DIR, 'weather.epw'),
    scenario_instructions=[s[0] for s in test_scenarios],
    baseline_period='warmest_week',
    scenario_period='warmest_week',
    raytracing_results_dir=os.path.join(JODLA_DIR, 'debug_raytracing_results')
)

# Override temp_work_dir to use our inspection directory
workflow.project_manager.temp_work_dir = temp_inspect_dir

print(f"\nTemp inspection directory: {temp_inspect_dir}")
print("(This will NOT be cleaned up so we can inspect the material files)\n")

# Get surfaces
surfaces = workflow.project_manager.identify_surfaces(use_baseline=True)
print(f"Found {len(surfaces['landscape'])} landscape surfaces")
print(f"Found {len(surfaces['facade'])} facade surfaces\n")

# Store material assignments for each scenario
scenario_materials = {}

for instruction, scenario_id in test_scenarios:
    print(f"\n{'='*70}")
    print(f"PROCESSING {scenario_id}: {instruction}")
    print(f"{'='*70}")
    
    # Create working copy
    work_dir = workflow.project_manager.create_working_copy(scenario_id)
    print(f"Created working copy: {work_dir}")
    
    # Get materials that should be used
    landscape_ratio, facade_ratio = instruction
    landscape_material = workflow.material_db.get_material_by_naturalness(landscape_ratio, 'landscape')
    facade_material = workflow.material_db.get_material_by_naturalness(facade_ratio, 'facade')
    
    print(f"\nExpected materials:")
    print(f"  Landscape ({landscape_ratio}): {landscape_material}")
    print(f"  Facade ({facade_ratio}): {facade_material}")
    
    # Apply material scenario
    workflow.project_manager.apply_material_scenario(
        instruction, 
        workflow.material_db, 
        surfaces, 
        scenario_id
    )
    
    # Read the modified geometry file
    work_scene_base = workflow.project_manager._get_work_scene_base()
    geometry_file = os.path.join(work_scene_base, "scene", "envelope.rad")
    
    if not os.path.exists(geometry_file):
        print(f"  ✗ ERROR: Geometry file not found: {geometry_file}")
        continue
    
    # Count material usage in the file
    with open(geometry_file, 'r') as f:
        geom_lines = f.readlines()
    
    # Extract material names (first token of each line that starts with a material)
    material_counts = {}
    for line in geom_lines:
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('!'):
            parts = line.split()
            if len(parts) > 0:
                mat_name = parts[0]
                material_counts[mat_name] = material_counts.get(mat_name, 0) + 1
    
    print(f"\nMaterial assignments in {scenario_id}:")
    for mat_name, count in sorted(material_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {mat_name}: {count} surfaces")
    
    scenario_materials[scenario_id] = {
        'instruction': instruction,
        'expected_landscape': landscape_material,
        'expected_facade': facade_material,
        'material_counts': material_counts,
        'geometry_file': geometry_file
    }
    
    # DON'T cleanup - we want to inspect the files
    # workflow.project_manager.cleanup_working_copy()

print(f"\n{'='*70}")
print("COMPARISON")
print(f"{'='*70}")

# Compare material assignments
s000_mats = set(scenario_materials['scenario_000']['material_counts'].keys())
s024_mats = set(scenario_materials['scenario_024']['material_counts'].keys())

print(f"\nMaterials in scenario_000: {len(s000_mats)} unique materials")
print(f"Materials in scenario_024: {len(s024_mats)} unique materials")
print(f"Common materials: {len(s000_mats & s024_mats)}")
print(f"Unique to scenario_000: {len(s000_mats - s024_mats)}")
print(f"Unique to scenario_024: {len(s024_mats - s000_mats)}")

if s000_mats != s024_mats:
    print(f"\n✓ PASS: Scenarios have DIFFERENT material assignments!")
    if s000_mats - s024_mats:
        print(f"  Materials only in scenario_000: {s000_mats - s024_mats}")
    if s024_mats - s000_mats:
        print(f"  Materials only in scenario_024: {s024_mats - s000_mats}")
else:
    print(f"\n✗ FAIL: Scenarios have IDENTICAL material assignments!")
    print(f"  This means the bug is still present - materials are not being changed")

# Compare specific material counts
print(f"\nMaterial count comparison:")
for mat_name in sorted(s000_mats | s024_mats):
    count_000 = scenario_materials['scenario_000']['material_counts'].get(mat_name, 0)
    count_024 = scenario_materials['scenario_024']['material_counts'].get(mat_name, 0)
    if count_000 != count_024:
        print(f"  {mat_name}: scenario_000={count_000}, scenario_024={count_024} (DIFFERENT)")
    elif count_000 > 0:
        print(f"  {mat_name}: both={count_000} (same)")

# Check if expected materials are present
print(f"\nExpected material check:")
for scenario_id, info in scenario_materials.items():
    print(f"\n{scenario_id}:")
    expected_landscape = info['expected_landscape']
    expected_facade = info['expected_facade']
    counts = info['material_counts']
    
    landscape_present = expected_landscape in counts
    facade_present = expected_facade in counts
    
    print(f"  Expected landscape '{expected_landscape}': {'✓' if landscape_present else '✗'} (count: {counts.get(expected_landscape, 0)})")
    print(f"  Expected facade '{expected_facade}': {'✓' if facade_present else '✗'} (count: {counts.get(expected_facade, 0)})")

print(f"\n{'='*70}")
print(f"Inspection files saved to: {temp_inspect_dir}")
print(f"You can manually inspect:")
print(f"  {os.path.join(temp_inspect_dir, 'scenario_000', 'scene', 'envelope.rad')}")
print(f"  {os.path.join(temp_inspect_dir, 'scenario_024', 'scene', 'envelope.rad')}")
print(f"{'='*70}")
