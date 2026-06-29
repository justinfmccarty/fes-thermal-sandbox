#!/usr/bin/env python3
"""
Verify Hour Indexing Fix

This script verifies that scenario feather files have data stored at the correct
calendar positions (same as baseline), not at indices 0-167.

After regenerating raytracing with the fix, this script will:
1. Load baseline and scenario feather files
2. Check that data is present at the warmest week calendar position
3. Check that data is NOT present at indices 0-167 (unless that IS the warmest week)
4. Verify that baseline - scenario produces meaningful differences

Usage:
    python verify_hour_indexing.py
"""

import os
import sys
import numpy as np
import pandas as pd

from config_locator import get_config, get_path
from weather_loader import find_warmest_day, get_week_around_day


def main():
    print("=" * 70)
    print("VERIFICATION: Hour Indexing Fix")
    print("=" * 70)
    
    # Get paths
    raytracing_dir = get_path('raytracing_results_dir')
    weather_path = get_path('weather_file')
    
    # Find warmest week dynamically
    day_of_year, _, warmest_date = find_warmest_day(weather_path)
    start_day, end_day = get_week_around_day(day_of_year)
    warmest_start = start_day * 24
    warmest_hours = (end_day - start_day + 1) * 24
    warmest_end = warmest_start + warmest_hours
    
    print(f"\nWarmest week: day {start_day+1}-{end_day+1}")
    print(f"Calendar hours: {warmest_start} to {warmest_end - 1}")
    print(f"Total hours: {warmest_hours}")
    
    # Load baseline
    baseline_path = os.path.join(raytracing_dir, 'baseline_direct.feather')
    if not os.path.exists(baseline_path):
        print("\nERROR: Baseline file not found!")
        return 1
    
    baseline_df = pd.read_feather(baseline_path).T  # Transpose: hours as rows
    print(f"\nBaseline shape: {baseline_df.shape}")
    
    # Check baseline has data at warmest week
    baseline_warmest = baseline_df.iloc[warmest_start:warmest_end]
    baseline_warmest_mean = baseline_warmest.mean().mean()
    print(f"Baseline warmest week mean: {baseline_warmest_mean:.2f} W/m²")
    
    # Check baseline January (hours 0-167)
    baseline_january = baseline_df.iloc[0:warmest_hours]
    baseline_january_mean = baseline_january.mean().mean()
    print(f"Baseline January (0-167) mean: {baseline_january_mean:.2f} W/m²")
    
    print("\n" + "-" * 50)
    print("Checking scenario files...")
    print("-" * 50)
    
    all_correct = True
    
    for i in range(25):
        scenario_id = f'scenario_{i:03d}'
        path = os.path.join(raytracing_dir, f'{scenario_id}_direct.feather')
        
        if not os.path.exists(path):
            print(f"\n{scenario_id}: SKIPPED (file not found)")
            continue
        
        scenario_df = pd.read_feather(path).T  # Transpose: hours as rows
        
        # Check at warmest week position
        scenario_warmest = scenario_df.iloc[warmest_start:warmest_end]
        scenario_warmest_mean = scenario_warmest.mean().mean()
        
        # Check at January position (should be empty/near-zero if warmest_start != 0)
        scenario_january = scenario_df.iloc[0:warmest_hours]
        scenario_january_mean = scenario_january.mean().mean()
        
        # Data should be at warmest week, not January (unless they're the same)
        warmest_has_data = scenario_warmest_mean > 1.0  # > 1 W/m² means real data
        january_has_data = scenario_january_mean > 1.0
        
        if warmest_start > 0:
            # Warmest week is NOT January
            if warmest_has_data and not january_has_data:
                status = "OK"
            elif not warmest_has_data and january_has_data:
                status = "WRONG (data at Jan, not warmest week)"
                all_correct = False
            elif warmest_has_data and january_has_data:
                status = "WRONG? (data at both - check manually)"
                all_correct = False
            else:
                status = "WRONG (no data anywhere)"
                all_correct = False
        else:
            # Warmest week IS January (rare but possible)
            if warmest_has_data:
                status = "OK (warmest=Jan)"
            else:
                status = "WRONG (no data)"
                all_correct = False
        
        print(f"\n{scenario_id}: {status}")
        print(f"   Warmest week ({warmest_start}-{warmest_end-1}): {scenario_warmest_mean:.2f} W/m²")
        print(f"   January (0-{warmest_hours-1}): {scenario_january_mean:.2f} W/m²")
        
        # Compare to baseline at same position
        diff = baseline_warmest_mean - scenario_warmest_mean
        print(f"   Diff from baseline: {diff:.2f} W/m²")
    
    print("\n" + "=" * 70)
    if all_correct:
        print("SUCCESS: All scenario files have data at correct calendar positions!")
    else:
        print("FAILURE: Some scenarios have incorrect indexing. Regenerate raytracing.")
    print("=" * 70)
    
    return 0 if all_correct else 1


if __name__ == '__main__':
    sys.exit(main())
