# Material Scenario Workflow for Tree Heat Stress Analysis

This workflow analyzes the impact of material choices (landscape surfaces and building facades) on tree heat stress by running multiple radiance simulations with different material scenarios.

## Overview

The workflow operates in **two phases**:

### Phase 1: Raytracing Simulations
1. Uses immutable `baseline_radiance_project/` as reference
2. Creates temporary working copies for each scenario
3. Generates material scenarios based on naturalness instructions (tuples of floats 0.0-1.0)
4. Runs radiance simulations for each scenario
5. Saves **only feather files** to `raytracing_results/` directory
6. Cleans up temporary working copies

### Phase 2: Tree Risk Analysis
1. Loads baseline and scenario feather files from `raytracing_results/`
2. Calculates heat stress for trees using nearest sensor lookup
3. Compares scenarios and identifies most impactful material choices

## Project Structure

```
jodla_project/
├── __init__.py                      # Package initialization
├── radiance.py                      # Local copy of radiance module
├── material_scenario_workflow.py   # Main workflow module
├── example_usage.py                 # Example script to run workflow
├── test_setup.py                    # Setup validation script
├── utils.py                         # Utility functions
├── config.yaml                      # Configuration file
├── README.md                        # Documentation
├── baseline_radiance_project/       # Immutable baseline project (reference)
│   └── model/                       # Radiance model files
├── scenario_radiance_project/       # Scenario source project (optimized grid files)
│   └── model/                       # Same structure but with faster grid files
└── raytracing_results/              # Feather files (created automatically)
    ├── baseline_direct.feather      # Baseline direct irradiance
    ├── baseline_diffuse.feather     # Baseline diffuse irradiance
    ├── scenario_XXX_direct.feather  # Scenario direct irradiance
    └── scenario_XXX_diffuse.feather # Scenario diffuse irradiance
    # Note: Total irradiance = direct + diffuse (calculated on-the-fly)
```

## Installation

Ensure you have the required dependencies:

```bash
pip install numpy pandas pyarrow scipy geopandas pyyaml
```

The workflow includes a local copy of `radiance.py` in this project directory.

## Quick Start

### 1. Test Setup

First, verify your setup is correct:

```bash
python test_setup.py
```

This will validate all input files and check coordinate ranges.

### 2. Setup Projects

Ensure you have both projects set up:

**Baseline Project** (`baseline_radiance_project/`):
- Immutable reference project
- Contains `model/scene/envelope.mat` and `envelope.rad`
- **Never modified** - used only for reference and surface identification

**Scenario Project** (`scenario_radiance_project/`):
- Source for creating scenario working copies
- Same structure as baseline but with **optimized grid files** for faster simulation
- Grid files should be more specific/sparse than baseline to speed up analysis

### 3. Configure Paths

Edit `config.yaml` or `example_usage.py` to set your project paths:
- Baseline project directory (defaults to `baseline_radiance_project/`)
- Tree points file (CSV with `xcoord`, `ycoord`, `zcoord`, and `number` or `tree_id` columns)
- Sensor points file (CSV with `x_coord`/`xcoord`, `y_coord`/`ycoord`, `z_coord`/`zcoord` columns)
- Weather file (EPW format)

**File Format Examples:**

Tree points CSV:
```csv
xcoord,ycoord,zcoord,number
634000.08,5518105.26,237.19,4937
634000.09,5518256.49,236.45,4013
...
```

Sensor points CSV:
```csv
x_coord,y_coord,z_coord,grid_name
33.55572,534.49188,2.71605,grid00_tall_grass
33.55572,535.49374,2.71605,grid00_tall_grass
...
```

### 4. Run Workflow

You can run the workflow in two ways:

**Option A: Run both phases together**
```python
from material_scenario_workflow import MaterialScenarioWorkflow

workflow = MaterialScenarioWorkflow(
    baseline_project_dir='baseline_radiance_project',  # Immutable reference
    scenario_project_dir='scenario_radiance_project',  # Source with optimized grids
    radiance_surface_key='',
    tree_points_file='/path/to/tree_points.csv',
    sensor_points_file='/path/to/sensor_points.csv',
    weather_file='/path/to/weather.epw'
)

results = workflow.run_full_workflow(
    n_scenarios=10,
    n_workers=6,
    use_accelerad=True  # Use GPU-accelerated Accelerad for faster raytracing
)
```

**Option B: Run phases separately** (recommended for large runs)
```python
# Phase 1: Generate feather files
scenario_feather_files = workflow.run_raytracing_phase(
    n_scenarios=10,
    n_workers=6,
    use_accelerad=True  # Use GPU-accelerated Accelerad for faster raytracing
)

# Phase 2: Analyze tree risk (can be run later)
results = workflow.run_tree_risk_analysis_phase(
    analysis_period=None,
    scenario_feather_files=scenario_feather_files
)
```

Or run the example script:

```bash
python example_usage.py
```

### 5. Define Scenario Instructions

You have two options for defining scenarios:

**Option A: Predefined scenarios** (recommended for reproducibility)
```python
# Define explicit scenario instructions
predefined_scenarios = [
    (0.0, 0.0),   # scenario_000: All concrete (worst case)
    (1.0, 0.0),   # scenario_001: Green landscape, concrete facades
    (0.0, 1.0),   # scenario_002: Concrete landscape, green facades
    (1.0, 1.0),   # scenario_003: All green (best case)
    (0.5, 0.5),   # scenario_004: 50/50 mix
]

workflow = MaterialScenarioWorkflow(
    ...,
    scenario_instructions=predefined_scenarios
)

# Or pass at runtime
workflow.run_raytracing_phase(scenario_instructions=predefined_scenarios)
```

**Option B: Random generation** (for exploration)
```python
# Don't provide scenario_instructions - will generate random scenarios
workflow = MaterialScenarioWorkflow(...)
workflow.run_raytracing_phase(n_scenarios=10)  # Generates 10 random scenarios
```

**Option C: Define in config.yaml**
```yaml
simulation:
  instructions:
    - [0.0, 0.0]  # All concrete
    - [1.0, 1.0]  # All green
    - [0.5, 0.5]  # 50/50 mix
```

Each instruction is a tuple `(landscape_naturalness, facade_naturalness)` where:
- `0.0` = least natural (all concrete)
- `1.0` = most natural (all vegetation/green walls)

## How It Works

### Material Scenarios

Each scenario is defined by an instruction tuple `(landscape_ratio, facade_ratio)`:
- `landscape_ratio`: Fraction of landscape surfaces that should be "more natural" (0.0 = all concrete, 1.0 = all vegetation)
- `facade_ratio`: Fraction of facade surfaces that should be "more natural" (0.0 = all concrete, 1.0 = all green walls)

For example, `(0.15, 0.95)` means:
- 15% of landscape surfaces remain less natural (concrete/asphalt)
- 95% of facade surfaces remain less natural (concrete)

### Material Database

Materials are weighted by "naturalness" score (0.0 = least natural, 1.0 = most natural):
- **Landscape**: concrete (0.0) → asphalt (0.2) → light pavement (0.4) → grass (0.8) → vegetation (1.0)
- **Facade**: concrete (0.0) → dark brick (0.3) → light brick (0.5) → green wall (0.9)

The workflow selects materials closest to the target naturalness ratio.

### Surface Identification

The workflow automatically identifies landscape vs facade surfaces from the geometry file (`envelope.rad`) by:
- Checking surface names for keywords (ground, terrain, pavement → landscape; wall, facade, building → facade)
- You may need to customize this logic based on your geometry naming conventions

### Tree Heat Stress Calculation

For each tree point:
1. Find nearest sensor point using spatial distance
2. Extract irradiance values (W/m²) for that sensor
3. Calculate heat stress metrics (currently uses maximum irradiance in analysis period)

### Analysis Period

By default, the workflow analyzes the warmest day in July. You can also specify a custom period:
```python
results = workflow.run_full_workflow(
    analysis_period=(4344, 4367)  # Specific 24-hour period
)
```

## Customization

### Adding Materials

Edit `setup_material_database()` in `material_scenario_workflow.py` or modify `config.yaml`:

```python
self.material_db.add_material(
    name='my_material',
    radiance_def='void plastic my_material\n0\n0\n5 0.5 0.5 0.5 0.0 0.0',
    naturalness=0.6,
    surface_type='landscape'
)
```

### Customizing Heat Stress Calculation

Modify the `calculate_heat_stress()` method in `TreeHeatStressCalculator` to implement your specific heat stress model.

### Surface Identification

Update `identify_surfaces()` in `RadianceProjectManager` to match your geometry file structure and naming conventions.

## Outputs

The workflow generates:
- **scenario_impacts_summary.csv**: Summary of all scenarios with average stress reduction per tree
- Individual risk analysis DataFrames for each scenario
- Results stored in `workflow.results` dictionary

## Important Notes

- **Baseline is immutable**: The `baseline_radiance_project/` directory is never modified and used only for reference
- **Scenario project has optimized grids**: The `scenario_radiance_project/` contains optimized grid files for faster simulation
- **Temporary working copies**: Each scenario creates a temporary copy from `scenario_radiance_project/` that is deleted after simulation
- **Only feather files saved**: Results are saved as feather files in `raytracing_results/` directory
- **Two-phase workflow**: Raytracing and analysis can be run separately, allowing you to:
  - Run raytracing for many scenarios over time
  - Analyze results later without re-running simulations
  - Re-analyze with different parameters using existing feather files
- **Grid file difference**: The scenario project uses more specific/sparse grid files to speed up simulation while maintaining accuracy for analysis
- Radiance simulations can be time-consuming; start with a small number of scenarios for testing
- Ensure both baseline and scenario radiance projects have been set up correctly before running scenarios

## Troubleshooting

1. **Import errors**: Ensure `radiance.py` is in the parent directory or adjust the import path
2. **Surface identification fails**: Check your geometry file structure and customize `identify_surfaces()`
3. **Tree/sensor point mismatch**: 
   - Verify coordinate systems match between tree points and sensor points
   - Run `test_setup.py` to check coordinate ranges
   - Tree points use UTM coordinates (e.g., 634000, 5518105)
   - Sensor points use local model coordinates (e.g., 33.5, 534.4)
   - The workflow uses spatial distance, so ensure they're in compatible coordinate systems
4. **Radiance simulation errors**: Check that radiance project structure matches expected format
5. **Column name errors**: The workflow handles both `xcoord`/`x_coord` formats automatically
6. **Accelerad not found**: 
   - Ensure Accelerad is installed and `accelerad_rfluxmtx.exe` is accessible
   - On Windows, install to `C:\Program Files\Accelerad\bin\` or add to PATH
   - Verify by running `accelerad_rfluxmtx` from command line
   - If Accelerad is not available, set `use_accelerad=False` (default) to use standard Radiance commands

## Example Output

```
Top 5 most impactful scenarios:
  1. scenario_003: 45.23 W/m² reduction
     Instruction: (0.85, 0.20)
  2. scenario_007: 42.15 W/m² reduction
     Instruction: (0.90, 0.15)
  ...
```

This indicates that scenarios with high landscape naturalness (85-90%) and low facade naturalness (15-20%) provide the most heat stress reduction for trees.

# Workflow
flowchart TD
    Start[Start] --> Baseline[Baseline Raytracing]
    Baseline --> BaselineFeather[baseline_direct.feather<br/>baseline_diffuse.feather]
    
    BaselineFeather --> Scenarios[Generate Scenarios]
    Scenarios --> ScenLoop{For each scenario}
    
    ScenLoop --> ModifyMat[Modify Materials<br/>based on instruction tuple]
    ModifyMat --> RunRad[Run Radiance Simulation]
    RunRad --> SaveFeather[Save scenario feather files]
    SaveFeather --> ScenLoop
    
    ScenLoop --> Analysis[Tree Risk Analysis Phase]
    
    Analysis --> LoadData[Load feather files +<br/>weather + species + grid mapping]
    LoadData --> BiophysModel[Biophysical Tree Stress Model]
    BiophysModel --> Metrics[Calculate Risk Metrics]
    Metrics --> Compare[Compare to Baseline]
    Compare --> Results[Results & Visualizations]