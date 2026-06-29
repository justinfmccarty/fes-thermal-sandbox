"""
Test script to verify setup and validate inputs before running full workflow
"""

import os
import sys
from utils import validate_inputs, load_tree_points, load_sensor_points

PROJECT_ROOT = '/Users/jmccarty/Nextcloud/Projects/35_UHI_Trees_Manitoba'
JODLA_PROJECT_DIR = os.path.join(PROJECT_ROOT, '00_data_code/jodla_project')

# Configuration
BASELINE_PROJECT_DIR = os.path.join(
    JODLA_PROJECT_DIR,
    'python/baseline_radiance_project'
)
SCENARIO_PROJECT_DIR = os.path.join(
    JODLA_PROJECT_DIR,
    'python/scenario_radiance_project'
)
TREE_POINTS_FILE = os.path.join(
    JODLA_PROJECT_DIR,
    'grid_records/baseline_trees.csv'
)
# Sensor points come from feather file column names after raytracing
# The .pts file is in correct Radiance format and only used by Radiance
SENSOR_POINTS_FILE = None
WEATHER_FILE = os.path.join(
    JODLA_PROJECT_DIR,
    'weather.epw'
)

def main():
    print("="*70)
    print("Testing Material Scenario Workflow Setup")
    print("="*70)
    
    # Validate inputs
    print("\n1. Validating inputs...")
    validation_baseline = validate_inputs(
        radiance_project_dir=BASELINE_PROJECT_DIR,
        tree_points_file=TREE_POINTS_FILE,
        sensor_points_file=SENSOR_POINTS_FILE,
        weather_file=WEATHER_FILE
    )
    
    validation_scenario = validate_inputs(
        radiance_project_dir=SCENARIO_PROJECT_DIR,
        tree_points_file=None,  # Don't re-check these
        sensor_points_file=None,
        weather_file=None
    )
    
    print(f"\n   Baseline project: {'✓' if validation_baseline['radiance_project'] else '✗'}")
    print(f"   Scenario project: {'✓' if validation_scenario['radiance_project'] else '✗'} (optional, uses baseline if missing)")
    print(f"   Tree points: {'✓' if validation_baseline['tree_points'] else '✗'}")
    print(f"   Sensor points: {'✓' if validation_baseline['sensor_points'] else '✗'}")
    print(f"   Weather file: {'✓' if validation_baseline['weather_file'] else '✗'}")
    
    all_errors = validation_baseline['errors'] + validation_scenario['errors']
    if all_errors:
        print("\n   Errors found:")
        for error in all_errors:
            print(f"     - {error}")
        if not validation_baseline['radiance_project']:
            return False  # Baseline is required
    
    # Test loading files
    print("\n2. Testing file loading...")
    try:
        tree_points = load_tree_points(TREE_POINTS_FILE)
        print(f"   ✓ Loaded {len(tree_points)} tree points")
        print(f"     Columns: {list(tree_points.columns)}")
        print(f"     Unique trees: {tree_points['tree_id'].nunique() if 'tree_id' in tree_points.columns else 'N/A'}")
    except Exception as e:
        print(f"   ✗ Error loading tree points: {e}")
        return False
    
    if SENSOR_POINTS_FILE:
        try:
            sensor_points = load_sensor_points(SENSOR_POINTS_FILE)
            print(f"   ✓ Loaded {len(sensor_points)} sensor points")
            print(f"     Columns: {list(sensor_points.columns)}")
        except Exception as e:
            print(f"   ✗ Error loading sensor points: {e}")
            return False
    else:
        print("   ⚠ Sensor points will be extracted from feather file after raytracing")
        sensor_points = None
    
    # Check coordinate ranges
    print("\n3. Checking coordinate ranges...")
    print(f"   Tree points:")
    print(f"     X: {tree_points['xcoord'].min():.2f} to {tree_points['xcoord'].max():.2f}")
    print(f"     Y: {tree_points['ycoord'].min():.2f} to {tree_points['ycoord'].max():.2f}")
    print(f"     Z: {tree_points['zcoord'].min():.2f} to {tree_points['zcoord'].max():.2f}")
    
    if sensor_points is not None:
        print(f"   Sensor points:")
        print(f"     X: {sensor_points['xcoord'].min():.2f} to {sensor_points['xcoord'].max():.2f}")
        print(f"     Y: {sensor_points['ycoord'].min():.2f} to {sensor_points['ycoord'].max():.2f}")
        print(f"     Z: {sensor_points['zcoord'].min():.2f} to {sensor_points['zcoord'].max():.2f}")
        
        # Check if coordinates overlap (they should be in similar ranges)
        tree_x_range = (tree_points['xcoord'].min(), tree_points['xcoord'].max())
        tree_y_range = (tree_points['ycoord'].min(), tree_points['ycoord'].max())
        sensor_x_range = (sensor_points['xcoord'].min(), sensor_points['xcoord'].max())
        sensor_y_range = (sensor_points['ycoord'].min(), sensor_points['ycoord'].max())
        
        x_overlap = not (tree_x_range[1] < sensor_x_range[0] or sensor_x_range[1] < tree_x_range[0])
        y_overlap = not (tree_y_range[1] < sensor_y_range[0] or sensor_y_range[1] < tree_y_range[0])
        
        if x_overlap and y_overlap:
            print("\n   ✓ Coordinate ranges overlap - spatial matching should work")
        else:
            print("\n   ⚠ Warning: Coordinate ranges don't overlap well - check coordinate systems")
    
    # Check radiance project structure
    print("\n4. Checking radiance project structure...")
    scene_dir = os.path.join(BASELINE_PROJECT_DIR, 'model', 'scene')
    if os.path.exists(scene_dir):
        mat_file = os.path.join(scene_dir, 'envelope.mat')
        rad_file = os.path.join(scene_dir, 'envelope.rad')
        
        if os.path.exists(mat_file):
            print(f"   ✓ Material file found: {mat_file}")
        else:
            print(f"   ✗ Material file not found: {mat_file}")
        
        if os.path.exists(rad_file):
            print(f"   ✓ Geometry file found: {rad_file}")
            # Count surfaces
            with open(rad_file, 'r') as f:
                lines = f.readlines()
                polygon_count = sum(1 for line in lines if 'polygon' in line.lower())
            print(f"     Found {polygon_count} polygon surfaces")
        else:
            print(f"   ✗ Geometry file not found: {rad_file}")
    
    print("\n" + "="*70)
    print("Setup test completed!")
    print("="*70)
    print("\nIf all checks passed, you can run the workflow with:")
    print("  python example_usage.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

