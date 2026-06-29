#!/usr/bin/env python3
"""
Test script to verify material application is working correctly.

This script:
1. Creates working copies for different scenarios
2. Applies materials
3. Verifies the materials are different between scenarios
4. Reports any issues
"""

import os
import sys
import tempfile
import shutil
from collections import Counter

from material_scenario_workflow import RadianceProjectManager, MaterialDatabase
from config_locator import get_config, get_path


def count_materials_in_file(filepath):
    """Count occurrences of each material in a Radiance geometry file."""
    materials = Counter()
    with open(filepath, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if parts and not line.strip().startswith('#'):
                materials[parts[0]] += 1
    return dict(materials)


def main():
    print("=" * 70)
    print("MATERIAL APPLICATION VERIFICATION TEST")
    print("=" * 70)
    print()
    
    # Load config
    config = get_config()
    
    # Use get_path for cross-platform compatibility
    baseline_dir = get_path('baseline_project_dir')
    scenario_dir = get_path('scenario_project_dir')
    
    print(f"Baseline project: {baseline_dir}")
    print(f"Scenario project: {scenario_dir}")
    print()
    
    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix='material_test_')
    print(f"Temp directory: {temp_dir}")
    print()
    
    try:
        # Create project manager
        pm = RadianceProjectManager(
            baseline_project_dir=baseline_dir,
            scenario_project_dir=scenario_dir,
            radiance_surface_key='',
            temp_work_dir=temp_dir
        )
        
        # Load material database
        mat_db_path = get_path('material_database_file')
        mat_db = MaterialDatabase(mat_db_path)
        
        # Test scenarios
        test_scenarios = [
            ('scenario_000', (0.0, 0.0)),   # All least natural
            ('scenario_012', (0.5, 0.5)),   # 50/50 mix
            ('scenario_024', (1.0, 1.0)),   # All most natural
        ]
        
        results = {}
        
        for scenario_id, instruction in test_scenarios:
            print(f"\n{'='*60}")
            print(f"TESTING {scenario_id}: instruction={instruction}")
            print(f"{'='*60}")
            
            # Create working copy
            work_dir = pm.create_working_copy(scenario_id)
            print(f"Working directory: {work_dir}")
            
            # Check envelope.rad path
            env_file = os.path.join(work_dir, 'scene', 'envelope.rad')
            if not os.path.exists(env_file):
                env_file = os.path.join(work_dir, 'model', 'scene', 'envelope.rad')
            
            print(f"Envelope file: {env_file}")
            print(f"File exists: {os.path.exists(env_file)}")
            
            if os.path.exists(env_file):
                # Count materials BEFORE
                materials_before = count_materials_in_file(env_file)
                print(f"\nMaterials BEFORE applying scenario:")
                for mat, count in sorted(materials_before.items()):
                    print(f"  {mat}: {count}")
                
                # Apply materials
                surfaces = pm.identify_surfaces(use_baseline=True)
                print(f"\nIdentified {len(surfaces['landscape'])} landscape and {len(surfaces['facade'])} facade surfaces")
                
                pm.apply_material_scenario(instruction, mat_db, surfaces, scenario_id)
                
                # Count materials AFTER
                materials_after = count_materials_in_file(env_file)
                print(f"\nMaterials AFTER applying scenario:")
                for mat, count in sorted(materials_after.items()):
                    print(f"  {mat}: {count}")
                
                results[scenario_id] = {
                    'instruction': instruction,
                    'materials_before': materials_before,
                    'materials_after': materials_after
                }
            
            # Clean up this working copy
            pm.cleanup_working_copy()
        
        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        
        all_same = True
        first_materials = None
        
        for scenario_id, data in results.items():
            if first_materials is None:
                first_materials = data['materials_after']
            else:
                if data['materials_after'] != first_materials:
                    all_same = False
            
            print(f"\n{scenario_id} {data['instruction']}:")
            print(f"  Materials: {data['materials_after']}")
        
        print("\n" + "=" * 70)
        if all_same:
            print("WARNING: All scenarios have IDENTICAL materials!")
            print("This indicates the material application is NOT working correctly.")
        else:
            print("SUCCESS: Scenarios have DIFFERENT materials!")
            print("Material application is working correctly.")
        print("=" * 70)
        
    finally:
        # Clean up
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"\nCleaned up temp directory: {temp_dir}")


if __name__ == '__main__':
    main()
