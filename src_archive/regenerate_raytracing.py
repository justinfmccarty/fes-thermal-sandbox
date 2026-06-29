#!/usr/bin/env python3
"""
Regenerate raytracing data for all scenarios.

This script:
1. Deletes existing scenario feather files (keeps baseline)
2. Re-runs raytracing for all 25 scenarios with proper material application
3. Verifies the results have different irradiance values

Usage:
    python regenerate_raytracing.py [--dry-run] [--verify-only]

Options:
    --dry-run       Show what would be deleted without actually deleting
    --verify-only   Only verify existing results, don't regenerate
"""

import os
import sys
import glob
import argparse
import numpy as np
import pandas as pd

from config_locator import get_config, get_path
from material_scenario_workflow import MaterialScenarioWorkflow


def delete_scenario_files(raytracing_dir, dry_run=False):
    """Delete existing scenario feather files."""
    print("\n" + "=" * 70)
    print("STEP 1: Delete existing scenario feather files")
    print("=" * 70)
    
    scenario_files = glob.glob(os.path.join(raytracing_dir, 'scenario_*.feather'))
    
    if not scenario_files:
        print("   No scenario files found to delete.")
        return
    
    print(f"   Found {len(scenario_files)} scenario files to delete:")
    for f in sorted(scenario_files)[:10]:
        print(f"      {os.path.basename(f)}")
    if len(scenario_files) > 10:
        print(f"      ... and {len(scenario_files) - 10} more")
    
    if dry_run:
        print("\n   [DRY RUN] Would delete these files, but not actually deleting.")
        return
    
    for f in scenario_files:
        os.remove(f)
        
    print(f"\n   Deleted {len(scenario_files)} files.")


def verify_results(raytracing_dir):
    """Verify raytracing results have different irradiance values."""
    print("\n" + "=" * 70)
    print("VERIFICATION: Check if scenarios have different irradiance")
    print("=" * 70)
    
    # Get warmest week dynamically from weather file
    from weather_loader import find_warmest_day, get_week_around_day
    weather_path = get_path('weather_file')
    day_of_year, _, warmest_date = find_warmest_day(weather_path)
    start_day, end_day = get_week_around_day(day_of_year)
    warmest_start = start_day * 24  # Dynamically calculated, not hardcoded
    warmest_hours = (end_day - start_day + 1) * 24
    
    print(f"   Warmest week: day {start_day+1}-{end_day+1} (hours {warmest_start}-{warmest_start + warmest_hours - 1})")
    
    # Load baseline
    baseline_path = os.path.join(raytracing_dir, 'baseline_direct.feather')
    if not os.path.exists(baseline_path):
        print("   ERROR: Baseline file not found!")
        return False
    
    baseline_df = pd.read_feather(baseline_path)
    baseline_week = baseline_df.T.iloc[warmest_start:warmest_start + warmest_hours]
    baseline_mean = baseline_week.mean().mean()
    print(f"   Baseline mean irradiance: {baseline_mean:.2f} W/m²")
    
    # Load scenarios - now using same calendar indexing as baseline
    scenario_means = {}
    for i in range(25):
        path = os.path.join(raytracing_dir, f'scenario_{i:03d}_direct.feather')
        if os.path.exists(path):
            df = pd.read_feather(path).T
            # Use same calendar indexing as baseline (data now at correct positions)
            scenario_week = df.iloc[warmest_start:warmest_start + warmest_hours]
            mean = scenario_week.mean().mean()
            scenario_means[f'scenario_{i:03d}'] = mean
    
    if not scenario_means:
        print("   No scenario files found!")
        return False
    
    print(f"\n   Scenario mean irradiance values:")
    unique_values = set()
    for sid, mean in sorted(scenario_means.items()):
        print(f"      {sid}: {mean:.2f} W/m²")
        unique_values.add(round(mean, 1))
    
    if len(unique_values) == 1:
        print(f"\n   WARNING: All {len(scenario_means)} scenarios have IDENTICAL irradiance!")
        print(f"   This indicates materials are NOT being applied correctly.")
        return False
    else:
        print(f"\n   SUCCESS: Scenarios have {len(unique_values)} different irradiance values!")
        print(f"   Materials are being applied correctly.")
        return True


def run_raytracing(use_accelerad=None):
    """Run raytracing for all scenarios.
    
    Args:
        use_accelerad: Override config setting. If None, uses config.simulation.use_accelerad
    """
    print("\n" + "=" * 70)
    print("STEP 2: Run raytracing for all scenarios")
    print("=" * 70)
    
    config = get_config()
    
    # Use config value if not explicitly specified
    if use_accelerad is None:
        use_accelerad = config.simulation.use_accelerad
    print(f"   Using Accelerad (GPU): {use_accelerad}")
    
    # Create the 25 scenarios
    predefined_scenarios = []
    for x in np.arange(0, 1.1, 0.25):
        for y in np.arange(0, 1.1, 0.25):
            predefined_scenarios.append((x, y))
    
    print(f"   Will generate {len(predefined_scenarios)} scenarios")
    
    # Initialize workflow (use get_path for cross-platform compatibility)
    workflow = MaterialScenarioWorkflow(
        baseline_project_dir=get_path('baseline_project_dir'),
        scenario_project_dir=get_path('scenario_project_dir'),
        tree_points_file=get_path('tree_points_file'),
        sensor_points_file=None,
        weather_file=get_path('weather_file'),
        scenario_instructions=predefined_scenarios,
        baseline_period='warmest_week',
        scenario_period='warmest_week'
    )
    
    # Run raytracing phase (skip baseline generation since it exists)
    workflow.run_raytracing_phase(
        n_workers=os.cpu_count()-2,
        generate_baseline_feather=True,  # Keep existing baseline
        use_accelerad=use_accelerad,
        force_regenerate=True  # Force regeneration even if files exist
    )
    
    print("\n   Raytracing complete!")


def main():
    parser = argparse.ArgumentParser(description='Regenerate raytracing data')
    parser.add_argument('--dry-run', action='store_true', 
                        help='Show what would be done without actually doing it')
    parser.add_argument('--verify-only', action='store_true',
                        help='Only verify existing results')
    parser.add_argument('--use-accelerad', action='store_true', default=None,
                        help='Use Accelerad (GPU) for faster raytracing (overrides config)')
    parser.add_argument('--no-accelerad', action='store_true',
                        help='Disable Accelerad (overrides config)')
    args = parser.parse_args()
    
    config = get_config()
    raytracing_dir = get_path('raytracing_results_dir')
    
    # Determine use_accelerad: command-line overrides config
    if args.use_accelerad:
        use_accelerad = True
    elif args.no_accelerad:
        use_accelerad = False
    else:
        use_accelerad = None  # Will use config default
    
    print("=" * 70)
    print("RAYTRACING REGENERATION SCRIPT")
    print("=" * 70)
    print(f"Raytracing directory: {raytracing_dir}")
    print(f"Accelerad (config): {config.simulation.use_accelerad}")
    
    if args.verify_only:
        verify_results(raytracing_dir)
        return
    
    if args.dry_run:
        print("\n[DRY RUN MODE - No changes will be made]")
    
    # Step 1: Delete old files
    delete_scenario_files(raytracing_dir, dry_run=args.dry_run)
    
    if args.dry_run:
        print("\n[DRY RUN] Would run raytracing here.")
        return
    
    # Step 2: Run raytracing
    run_raytracing(use_accelerad=use_accelerad)
    
    # Step 3: Verify results
    verify_results(raytracing_dir)
    
    print("\n" + "=" * 70)
    print("REGENERATION COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
