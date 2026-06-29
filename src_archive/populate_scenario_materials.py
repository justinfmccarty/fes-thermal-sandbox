"""
Script to populate scenario_grid_materials.csv with actual material assignments.

This reads the 25 scenario instructions, calculates the coverage fractions needed
to achieve each target average naturalness, and assigns materials accordingly.

Uses THREE-TIER interpolation (same as material_scenario_workflow.py):
- For targets <= 0.95: interpolate between black_brick (0.15) + short_grass (0.95)
- For targets > 0.95: interpolate between short_grass (0.95) + tall_grass (1.0)
- Surfaces are randomly selected (with deterministic seed) to receive each material
"""

import pandas as pd
import numpy as np
import os
import random
import hashlib
from material_scenario_workflow import MaterialDatabase


def main():
    # Load baseline materials to get ground_or_facade info and areas
    baseline_df = pd.read_csv('grid_records/baseline_materials.csv')
    print(f"Loaded {len(baseline_df)} baseline surfaces")
    print(f"  Ground: {(baseline_df['ground_or_facade'] == 'ground').sum()}")
    print(f"  Facade: {(baseline_df['ground_or_facade'] == 'facade').sum()}")
    
    # Load material database
    mat_db = MaterialDatabase(root_material_db_path='root_material_database.csv')
    print(f"\nLoaded {len(mat_db.materials)} materials from database")
    
    # Show three-tier materials
    print("\nThree-tier material system:")
    for surface_type in ['landscape', 'facade']:
        least = mat_db.get_least_natural(surface_type)
        try:
            mid, mid_n = mat_db.get_material_with_naturalness('short_grass', surface_type)
        except:
            mid, mid_n = "N/A", 0.0
        most, most_n = mat_db.get_most_natural(surface_type)
        least_n = next(m['naturalness'] for m in mat_db.materials 
                       if m['name'] == least and m['surface_type'] == surface_type)
        print(f"  {surface_type}: {least} ({least_n}) -> {mid} ({mid_n}) -> {most} ({most_n})")
    
    # Create 25 scenarios (same as in workflow.py)
    predefined_scenarios = []
    for x in np.arange(0, 1.1, 0.25):
        for y in np.arange(0, 1.1, 0.25):
            predefined_scenarios.append((x, y))
    
    print(f"\nGenerating material assignments for {len(predefined_scenarios)} scenarios")
    
    # Create output dataframe
    output_rows = []
    
    # First, add baseline (unchanged)
    for _, row in baseline_df.iterrows():
        output_rows.append({
            'scenario_id': 'baseline',
            'grid_id': row['grid_id'],
            'material_name': row['material_name'],
            'area_m2': row['area_m2'],
            'ground_or_facade': row['ground_or_facade']
        })
    
    # Get surface lists
    ground_surfaces = baseline_df[baseline_df['ground_or_facade'] == 'ground'].copy()
    facade_surfaces = baseline_df[baseline_df['ground_or_facade'] == 'facade'].copy()
    n_ground = len(ground_surfaces)
    n_facade = len(facade_surfaces)
    
    # Then add all scenarios
    for i, (landscape_ratio, facade_ratio) in enumerate(predefined_scenarios):
        scenario_id = f"scenario_{i:03d}"
        
        # Seed random number generator for reproducibility (same as workflow.py)
        seed = int(hashlib.md5(scenario_id.encode()).hexdigest(), 16) % (2**32)
        random.seed(seed)
        
        # THREE-TIER MATERIAL SELECTION
        # Get materials and coverage for landscape
        landscape_lower, landscape_upper, landscape_upper_coverage = \
            mat_db.calculate_three_tier_coverage(landscape_ratio, 'landscape')
        
        # Get materials and coverage for facade
        facade_lower, facade_upper, facade_upper_coverage = \
            mat_db.calculate_three_tier_coverage(facade_ratio, 'facade')
        
        # Number of surfaces to get the UPPER material in each tier
        n_ground_upper = int(n_ground * landscape_upper_coverage)
        n_facade_upper = int(n_facade * facade_upper_coverage)
        
        # Randomly select which surfaces get UPPER material
        ground_indices = list(ground_surfaces.index)
        ground_to_upper = random.sample(ground_indices, n_ground_upper) if n_ground_upper > 0 else []
        ground_to_lower = [idx for idx in ground_indices if idx not in ground_to_upper]
        
        facade_indices = list(facade_surfaces.index)
        facade_to_upper = random.sample(facade_indices, n_facade_upper) if n_facade_upper > 0 else []
        facade_to_lower = [idx for idx in facade_indices if idx not in facade_to_upper]
        
        # Get naturalness scores for actual average calculation
        landscape_upper_n = next(m['naturalness'] for m in mat_db.materials 
                                  if m['name'] == landscape_upper and m['surface_type'] == 'landscape')
        landscape_lower_n = next(m['naturalness'] for m in mat_db.materials 
                                  if m['name'] == landscape_lower and m['surface_type'] == 'landscape')
        facade_upper_n = next(m['naturalness'] for m in mat_db.materials 
                              if m['name'] == facade_upper and m['surface_type'] == 'facade')
        facade_lower_n = next(m['naturalness'] for m in mat_db.materials 
                              if m['name'] == facade_lower and m['surface_type'] == 'facade')
        
        # Calculate actual average naturalness achieved
        actual_landscape_avg = (n_ground_upper * landscape_upper_n + 
                                (n_ground - n_ground_upper) * landscape_lower_n) / n_ground if n_ground > 0 else 0
        actual_facade_avg = (n_facade_upper * facade_upper_n + 
                             (n_facade - n_facade_upper) * facade_lower_n) / n_facade if n_facade > 0 else 0
        
        print(f"  {scenario_id}: target=({landscape_ratio:.2f}, {facade_ratio:.2f}) -> "
              f"materials=({landscape_lower}+{landscape_upper}, {facade_lower}+{facade_upper}) -> "
              f"actual_avg=({actual_landscape_avg:.3f}, {actual_facade_avg:.3f})")
        
        # Assign materials to ground surfaces
        for idx in ground_to_upper:
            row = baseline_df.loc[idx]
            output_rows.append({
                'scenario_id': scenario_id,
                'grid_id': row['grid_id'],
                'material_name': landscape_upper,
                'area_m2': row['area_m2'],
                'ground_or_facade': row['ground_or_facade']
            })
        
        for idx in ground_to_lower:
            row = baseline_df.loc[idx]
            output_rows.append({
                'scenario_id': scenario_id,
                'grid_id': row['grid_id'],
                'material_name': landscape_lower,
                'area_m2': row['area_m2'],
                'ground_or_facade': row['ground_or_facade']
            })
        
        # Assign materials to facade surfaces
        for idx in facade_to_upper:
            row = baseline_df.loc[idx]
            output_rows.append({
                'scenario_id': scenario_id,
                'grid_id': row['grid_id'],
                'material_name': facade_upper,
                'area_m2': row['area_m2'],
                'ground_or_facade': row['ground_or_facade']
            })
        
        for idx in facade_to_lower:
            row = baseline_df.loc[idx]
            output_rows.append({
                'scenario_id': scenario_id,
                'grid_id': row['grid_id'],
                'material_name': facade_lower,
                'area_m2': row['area_m2'],
                'ground_or_facade': row['ground_or_facade']
            })
    
    # Create dataframe and save
    output_df = pd.DataFrame(output_rows)
    output_path = 'grid_records/scenario_grid_materials.csv'
    output_df.to_csv(output_path, index=False)
    
    print(f"\n✅ Successfully created {output_path}")
    print(f"   Total rows: {len(output_df)}")
    print(f"   Scenarios: {output_df['scenario_id'].nunique()} (baseline + {len(predefined_scenarios)} scenarios)")
    print(f"   Grids per scenario: {len(baseline_df)}")
    
    # Show sample
    print(f"\nSample rows for scenario_000 (target 0.0, 0.0 - all least natural):")
    print(output_df[output_df['scenario_id'] == 'scenario_000'].head(10))
    
    print(f"\nSample rows for scenario_024 (target 1.0, 1.0 - all most natural):")
    print(output_df[output_df['scenario_id'] == 'scenario_024'].head(10))
    
    # Show summary statistics
    print("\nMaterial distribution for scenario_000 (target 0.0):")
    scenario_000 = output_df[output_df['scenario_id'] == 'scenario_000']
    material_counts = scenario_000.groupby(['ground_or_facade', 'material_name']).size()
    print(material_counts)
    
    print("\nMaterial distribution for scenario_012 (target 0.5, 0.5):")
    scenario_012 = output_df[output_df['scenario_id'] == 'scenario_012']
    material_counts = scenario_012.groupby(['ground_or_facade', 'material_name']).size()
    print(material_counts)
    
    # Find scenario with target ~0.95 (should be 100% short_grass)
    # scenario_019 = (0.75, 1.0), scenario_023 = (1.0, 0.75)
    # Actually we need a scenario that's exactly 0.95 - let's check scenario_019 which is (0.75, 1.0)
    print("\nMaterial distribution for scenario_019 (target 0.75, 1.0):")
    scenario_019 = output_df[output_df['scenario_id'] == 'scenario_019']
    material_counts = scenario_019.groupby(['ground_or_facade', 'material_name']).size()
    print(material_counts)
    
    print("\nMaterial distribution for scenario_024 (target 1.0, 1.0):")
    scenario_024 = output_df[output_df['scenario_id'] == 'scenario_024']
    material_counts = scenario_024.groupby(['ground_or_facade', 'material_name']).size()
    print(material_counts)


if __name__ == '__main__':
    main()
