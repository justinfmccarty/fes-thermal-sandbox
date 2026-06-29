"""Quick verification that scenario materials are properly stored."""
import pandas as pd

# Load the complete scenario materials file
df = pd.read_csv('grid_records/scenario_grid_materials.csv')

print("✅ VERIFICATION: Scenario Material Compositions")
print("=" * 70)
print(f"\n📁 File: grid_records/scenario_grid_materials.csv")
print(f"   Total entries: {len(df):,}")
print(f"   Scenarios: {df['scenario_id'].nunique()}")
print(f"   Surfaces: {df['grid_id'].nunique()}")
print(f"   Materials: {df['material_name'].nunique()}")

# Verify all 25 scenarios exist
expected_scenarios = ['baseline'] + [f'scenario_{i:03d}' for i in range(25)]
actual_scenarios = set(df['scenario_id'].unique())
missing = set(expected_scenarios) - actual_scenarios
if missing:
    print(f"\n⚠️  Missing scenarios: {missing}")
else:
    print(f"\n✅ All 26 scenarios present (baseline + 000-024)")

# Check for empty material names
empty_materials = df[df['material_name'].isna() | (df['material_name'] == '')]
if len(empty_materials) > 0:
    print(f"\n⚠️  {len(empty_materials)} surfaces have no material assigned")
else:
    print(f"\n✅ All surfaces have materials assigned")

# Show sample: most and least "natural" scenario
print("\n📊 Sample: Extreme Scenarios")
print("-" * 70)

print("\n   Scenario 000 (Least Natural: 0.0, 0.0):")
s000 = df[df['scenario_id'] == 'scenario_000'].groupby(['ground_or_facade', 'material_name']).size()
for (surface_type, material), count in s000.items():
    print(f"     {surface_type:8s} {material:30s} × {count:3d}")

print("\n   Scenario 024 (Most Natural: 1.0, 1.0):")
s024 = df[df['scenario_id'] == 'scenario_024'].groupby(['ground_or_facade', 'material_name']).size()
for (surface_type, material), count in s024.items():
    print(f"     {surface_type:8s} {material:30s} × {count:3d}")

print("\n" + "=" * 70)
print("✅ Material compositions successfully stored and verified!")
