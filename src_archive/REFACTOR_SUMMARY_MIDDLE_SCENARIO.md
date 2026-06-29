# Refactor Summary: Shift to Middle Scenario Reference

**Date**: 2026-01-12  
**File Modified**: `run_analysis.py`

## Overview

Successfully refactored the analysis pipeline to use **scenario_012 (50% landscape, 50% facade)** as the reference point instead of baseline. The baseline scenario is now completely excluded from analysis.

## Changes Made

### 1. Section 1: Biophysical Analysis (Lines 99-227)
- **Line 168**: Removed 'baseline' from scenario_ids list
- Now processes only: `scenario_000` through `scenario_024` (25 scenarios)

### 2. Section 2: Stress Summaries (Lines 277-322)
- **Lines 299-310**: Removed special handling for baseline scenario
- All scenarios now get landscape/facade ratios from scenario mapping
- No more NaN values for baseline

### 3. Section 3: Percent Change Calculation (Lines 323-402)
- **Line 325**: Updated docstring to reference middle scenario
- **Line 331**: Print header now says "NORMALIZED PERCENT CHANGE FROM MIDDLE SCENARIO"
- **Lines 334-345**: Changed from `baseline_data` and `baseline_means` to `middle_data` and `middle_means`
  - Reference: `master_summary[master_summary['scenario_id'] == 'scenario_012']`
- **Line 347**: Print statement now says "Middle scenario (50%, 50%) means:"
- **Line 369**: Changed loop to use `middle_means` instead of `baseline_means`
- **Line 374**: Percent change formula: `(scenario_mean - middle_val) / abs(middle_val) * 100`
  - For scenario_012: this yields exactly 0% (comparing to itself)

### 4. Section 5: Plot Generation (Lines 533-748)

#### Plot 1 - Heatmap (Line 581)
- Title: "Percent Change in Tree Risk Index\n(Relative to Middle Scenario 50%/50%)"

#### Plot 3 - Box Plot (Lines 636-664)
- Removed 'baseline' from key_scenarios list
- Updated label for scenario_012: "S012 - Middle\n(50%, 50%)"
- Adjusted colors array (removed baseline color)

#### Plot 4 - Bar Chart (Line 689)
- Title: "Top 5 Best and Worst Scenarios for Tree Risk (vs Middle 50%/50%)"

#### Plot 5 - MRT/Tsurf Heatmaps (Line 735)
- Title template: "% Change in {title} (vs Middle 50%/50%)"

### 5. Section 6: Report Generation (Lines 747-847)

#### Summary Statistics (Lines 759-770)
- Added explicit note: "Reference scenario: scenario_012 (50% landscape, 50% facade)"
- Changed "Baseline Conditions" to "Middle Scenario (50%, 50%) - Reference Conditions"
- Uses `master_summary[master_summary['scenario_id'] == 'scenario_012']` for reference values

#### Key Findings (Lines 773-783)
- Section title: "Risk Index Changes (Relative to Middle Scenario)"
- Updated labels: "Best scenario (lowest risk vs middle)" and "Worst scenario (highest risk vs middle)"

#### Recommendations (Lines 806-830)
- Rewritten to describe changes relative to middle scenario
- Now says "Based on comparison to the middle scenario (50%/50%):"
- Updated logic to explain scenarios that reduce/increase stress relative to middle scenario

#### Output Files (Lines 833-838)
- Updated description: "Scenario-level percent changes from middle scenario (50%/50%)"
- Added note: "Baseline scenario is not included in this analysis. All comparisons are relative to scenario_012 (50% landscape, 50% facade)."

## Validation Results

✓ **Percent Change Logic**: scenario_012 compared to itself yields exactly 0% for all metrics  
✓ **Terminology**: All references use "middle scenario", "50%/50%", or "scenario_012"  
✓ **Baseline Exclusion**: Baseline is not processed or referenced (except in explanatory notes)  
✓ **Linter**: No errors introduced  
✓ **Total Scenarios**: 25 scenarios analyzed (scenario_000 to scenario_024)

## Expected Behavior

When running `run_analysis.py`:

1. **Biophysical Analysis**: Processes 25 scenarios (no baseline)
2. **Stress Summaries**: All scenarios have numeric landscape/facade ratios
3. **Percent Change**: scenario_012 shows 0.00% change for all metrics
4. **Plots**: 
   - Heatmaps centered on 0% (scenario_012 location)
   - Box plot shows scenario_012 as reference
   - All titles reference "vs Middle 50%/50%"
5. **Report**: 
   - References scenario_012 as the comparison point
   - Explains scenarios better/worse than middle scenario
   - Notes that baseline is excluded

## Files Modified

- `run_analysis.py` - Primary analysis script (all changes implemented)

## Files NOT Modified

- `config.yaml` - Scenario definitions remain unchanged
- Biophysical calculation modules - Work independently
- Raytracing results - Already generated (just skip loading baseline)
- Material database files - Unchanged

## Migration Notes

Users should:
1. Re-run the analysis to generate new outputs with middle scenario reference
2. Update any external documentation referring to baseline comparisons
3. Interpret results as changes relative to the 50%/50% mixed scenario

## Key Insight

Using scenario_012 (50%/50%) as reference provides a more meaningful comparison than baseline:
- Represents a balanced mid-point in the design space
- Shows which material strategies perform better/worse than a moderate intervention
- Baseline was proving difficult to work with - middle scenario provides clearer insights
