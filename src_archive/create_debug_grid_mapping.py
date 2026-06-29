#!/usr/bin/env python3
"""
Create grid material mapping for debug scenarios.
This generates a CSV file with material assignments for scenario_000, scenario_012, and scenario_024
based on the baseline materials and scenario instructions.
"""

import os
import pandas as pd
from material_scenario_workflow import MaterialDatabase

# Configuration
user_folder = '/Users/jmccarty'
PROJECT_ROOT = os.path.join(user_folder, 'Nextcloud', 'Projects', '35_UHI_Trees_Manitoba')
JODLA_DIR = os.path.join(PROJECT_ROOT, '00_data_code', 'jodla_project')

# Debug scenarios
debug_scenarios = [
    ('scenario_000', (0.0, 0.0)),  # Least natural
    ('scenario_012', (0.5, 0.5)),  # Mixed
    ('scenario_024', (1.0, 1.0))   # Most natural
]

print("Creating debug grid material mapping...")

# Load baseline materials
baseline_path = os.path.join(JODLA_DIR, 'grid_records', 'baseline_materials.csv')
baseline_df = pd.read_csv(baseline_path)
print(f"Loaded {len(baseline_df)} baseline material assignments")

# Load material database (same way as workflow does)
root_db_path = os.path.join(JODLA_DIR, 'root_material_database.csv')
material_db = MaterialDatabase(root_material_db_path=root_db_path if os.path.exists(root_db_path) else None)

# Create output DataFrame
output_rows = []

# Add baseline entries
for _, row in baseline_df.iterrows():
    output_rows.append({
        'scenario_id': 'baseline',
        'grid_id': row['grid_id'],
        'material_name': row['material_name'],
        'area_m2': row['area_m2'],
        'ground_or_facade': row['ground_or_facade']
    })

# Add debug scenario entries
for scenario_id, (landscape_ratio, facade_ratio) in debug_scenarios:
    print(f"\nProcessing {scenario_id}: ({landscape_ratio}, {facade_ratio})")
    
    # Get materials for this scenario
    landscape_material = material_db.get_material_by_naturalness(landscape_ratio, 'landscape')
    facade_material = material_db.get_material_by_naturalness(facade_ratio, 'facade')
    least_natural_landscape = material_db.get_least_natural('landscape')
    least_natural_facade = material_db.get_least_natural('facade')
    
    print(f"  Landscape material: {landscape_material}")
    print(f"  Facade material: {facade_material}")
    print(f"  Least natural landscape: {least_natural_landscape}")
    print(f"  Least natural facade: {least_natural_facade}")
    
    # Determine how many surfaces should be natural vs less natural
    ground_surfaces = baseline_df[baseline_df['ground_or_facade'] == 'ground']
    facade_surfaces = baseline_df[baseline_df['ground_or_facade'] == 'facade']
    
    n_ground = len(ground_surfaces)
    n_facade = len(facade_surfaces)
    
    n_ground_natural = int(n_ground * landscape_ratio)
    n_facade_natural = int(n_facade * facade_ratio)
    
    # Select which ground surfaces get natural material (deterministic based on scenario_id)
    import hashlib
    seed = int(hashlib.md5(scenario_id.encode()).hexdigest(), 16) % (2**32)
    import random
    random.seed(seed)
    
    ground_indices = list(ground_surfaces.index)
    ground_to_natural = random.sample(ground_indices, n_ground_natural) if n_ground_natural > 0 else []
    ground_to_less_natural = [i for i in ground_indices if i not in ground_to_natural]
    
    facade_indices = list(facade_surfaces.index)
    facade_to_natural = random.sample(facade_indices, n_facade_natural) if n_facade_natural > 0 else []
    facade_to_less_natural = [i for i in facade_indices if i not in facade_to_natural]
    
    # Assign materials to ground surfaces
    for idx in ground_to_natural:
        row = ground_surfaces.loc[idx]
        output_rows.append({
            'scenario_id': scenario_id,
            'grid_id': row['grid_id'],
            'material_name': landscape_material,
            'area_m2': row['area_m2'],
            'ground_or_facade': 'ground'
        })
    
    for idx in ground_to_less_natural:
        row = ground_surfaces.loc[idx]
        output_rows.append({
            'scenario_id': scenario_id,
            'grid_id': row['grid_id'],
            'material_name': least_natural_landscape,
            'area_m2': row['area_m2'],
            'ground_or_facade': 'ground'
        })
    
    # Assign materials to facade surfaces
    for idx in facade_to_natural:
        row = facade_surfaces.loc[idx]
        output_rows.append({
            'scenario_id': scenario_id,
            'grid_id': row['grid_id'],
            'material_name': facade_material,
            'area_m2': row['area_m2'],
            'ground_or_facade': 'facade'
        })
    
    for idx in facade_to_less_natural:
        row = facade_surfaces.loc[idx]
        output_rows.append({
            'scenario_id': scenario_id,
            'grid_id': row['grid_id'],
            'material_name': least_natural_facade,
            'area_m2': row['area_m2'],
            'ground_or_facade': 'facade'
        })
    
    print(f"  Created {len(ground_to_natural) + len(ground_to_less_natural)} ground assignments")
    print(f"  Created {len(facade_to_natural) + len(facade_to_less_natural)} facade assignments")

# Create output DataFrame
output_df = pd.DataFrame(output_rows)

# Save to debug grid mapping file
output_path = os.path.join(JODLA_DIR, 'grid_records', 'debug_scenario_grid_materials.csv')
output_df.to_csv(output_path, index=False)
print(f"\n✓ Saved debug grid material mapping to: {output_path}")
print(f"  Total rows: {len(output_df)}")
print(f"  Scenarios: {output_df['scenario_id'].nunique()}")
print(f"  Unique materials: {output_df['material_name'].nunique()}")

# Also update the main scenario_grid_materials.csv to include debug scenarios
main_path = os.path.join(JODLA_DIR, 'grid_records', 'scenario_grid_materials.csv')
if os.path.exists(main_path):
    main_df = pd.read_csv(main_path)
    # Remove any existing debug scenario entries
    main_df = main_df[~main_df['scenario_id'].isin([s[0] for s in debug_scenarios])]
    # Add debug scenario entries
    debug_df = output_df[output_df['scenario_id'].isin([s[0] for s in debug_scenarios])]
    combined_df = pd.concat([main_df, debug_df], ignore_index=True)
    combined_df.to_csv(main_path, index=False)
    print(f"\n✓ Updated {main_path} with debug scenarios")
    print(f"  Total rows: {len(combined_df)}")
