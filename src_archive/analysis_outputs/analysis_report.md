# Tree Stress Analysis Report

Generated: 2026-01-12 22:12:09

Data source: `/Users/jmccarty/Nextcloud/Projects/35_UHI_Trees_Manitoba/00_data_code/jodla_project/raytracing_results`

## Summary Statistics

- Total scenarios analyzed: 25
- Total trees per scenario: 147
- Reference scenario: scenario_012 (50% landscape, 50% facade)

### Middle Scenario (50%, 50%) - Reference Conditions

- Mean T_leaf: 23.81°C
- Mean MRT: 22.61°C
- Mean Tsurf: 24.49°C
- Mean Degree Hours: 25.63

## Key Findings

### Risk Index Changes (Relative to Middle Scenario)

- **Best scenario** (lowest risk vs middle): scenario_004 (Landscape: 100%, Facade: 0%)
  - Risk change: -5.21%
- **Worst scenario** (highest risk vs middle): scenario_020 (Landscape: 0%, Facade: 100%)
  - Risk change: 12.76%

### Sensitivity Analysis

**Risk vs Albedo:**
- Slope: 61.04 %/unit
- R²: 0.871
- p-value: 0.0000

**Risk vs Emissivity:**
- Slope: -194.21 %/unit
- R²: 0.638
- p-value: 0.0000

**Tsurf vs Albedo:**
- Slope: -89.39 %/unit
- R²: 0.898
- p-value: 0.0000

## Recommendations

Based on comparison to the middle scenario (50%/50%):
1. **Some scenarios reduce tree stress below the middle scenario**. The best scenario (scenario_004) shows a 5.2% reduction.
2. **Some scenarios increase tree stress above the middle scenario**. The worst scenario (scenario_020) shows a 12.8% increase.
3. **Landscape vegetation has a stronger effect** than facade vegetation on tree stress (range: 13.0% vs 4.9%).

## Output Files

- `/Users/jmccarty/Nextcloud/Projects/35_UHI_Trees_Manitoba/00_data_code/jodla_project/analysis_outputs/stress_summary_all_scenarios.csv` - Per-tree stress metrics for all scenarios
- `/Users/jmccarty/Nextcloud/Projects/35_UHI_Trees_Manitoba/00_data_code/jodla_project/analysis_outputs/pct_change_summary.csv` - Scenario-level percent changes from middle scenario (50%/50%)
- `/Users/jmccarty/Nextcloud/Projects/35_UHI_Trees_Manitoba/00_data_code/jodla_project/analysis_outputs/sensitivity_analysis.csv` - Material properties and regression results
- `/Users/jmccarty/Nextcloud/Projects/35_UHI_Trees_Manitoba/00_data_code/jodla_project/analysis_outputs/plots/` - Publication-quality figures

**Note**: Baseline scenario is not included in this analysis. All comparisons are relative to scenario_012 (50% landscape, 50% facade).