# Plot Formatting Guide

Comprehensive guide for standardized plot formatting in the JODLA project.

## Quick Start

```python
from plot_formatting import format_plot, set_project_style

# Set project style globally
set_project_style('default')

# Create and format a plot
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.plot(x, y)
format_plot(ax, xlabel='X', ylabel='Y', title='My Plot')
plt.show()
```

## Table of Contents

1. [Basic Usage](#basic-usage)
2. [Style Presets](#style-presets)
3. [Color Schemes](#color-schemes)
4. [Specialized Functions](#specialized-functions)
5. [Integration with run_analysis.py](#integration-with-run_analysispy)

---

## Basic Usage

### Setting Global Style

```python
from plot_formatting import set_project_style

# Options: 'default', 'presentation', 'paper', 'poster'
set_project_style('default')
```

### Formatting Individual Plots

```python
from plot_formatting import format_plot
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(8, 6))
ax.plot(x, y, 'o-')

format_plot(
    ax,
    xlabel='X Axis Label',
    ylabel='Y Axis Label',
    title='Plot Title',
    xlim=(0, 10),
    ylim=(0, 100),
    grid=True,
    legend=True
)
```

### Default Style Features

- **Ticks**: Inward-facing, 4pt length
- **Grid**: Light grey (#lightgrey), 0.3 alpha, 0.5 linewidth
- **Spines**: Top and right spines hidden by default
- **Font**: Sans-serif (Arial/Helvetica), size 11
- **Legend**: Frameless, auto-positioned

---

## Style Presets

### Default Style
```python
set_project_style('default')
# Font size: 11, Label size: 12, Title size: 14
# Good for: Jupyter notebooks, general analysis
```

### Paper Style
```python
set_project_style('paper')
# Font size: 9, Label size: 10, Title size: 11
# DPI: 600 for high-quality publication
# Good for: Journal submissions, compact figures
```

### Presentation Style
```python
set_project_style('presentation')
# Font size: 14, Label size: 16, Title size: 18
# Thicker lines (2.0) and larger markers (8)
# Good for: PowerPoint slides, talks
```

### Poster Style
```python
set_project_style('poster')
# Font size: 18, Label size: 22, Title size: 26
# Very thick lines (3.0) and large markers (12)
# Good for: Conference posters, large displays
```

### Temporary Style Context

```python
from plot_formatting import PlotStyle

# Temporarily use presentation style
with PlotStyle('presentation'):
    fig, ax = plt.subplots()
    ax.plot(x, y)
    format_plot(ax, title='Presentation Plot')
# Automatically reverts to previous style after block
```

---

## Color Schemes

### Accessing Project Colors

```python
from plot_formatting import get_project_colors

# Get all colors
colors = get_project_colors()

# Get specific color
blue = get_project_colors('primary_blue')  # Returns '#2E5C8A'
```

### Available Colors

#### Primary Colors
- `primary_blue`: #2E5C8A
- `primary_green`: #2D8659
- `primary_red`: #C44E4E
- `primary_yellow`: #D4A942
- `primary_purple`: #7B5F9E

#### Scenario Colors (Vegetation Coverage)
- `low_vegetation`: #E74C3C (Red - 0%)
- `mid_low`: #F39C12 (Orange - 25%)
- `middle`: #F1C40F (Yellow - 50%)
- `mid_high`: #2ECC71 (Light green - 75%)
- `high_vegetation`: #27AE60 (Green - 100%)

#### Neutral Colors
- `dark_grey`: #2C3E50
- `medium_grey`: #7F8C8D
- `light_grey`: #BDC3C7
- `very_light_grey`: #ECF0F1
- `white`: #FFFFFF

### Colormaps

```python
from plot_formatting import get_project_colormaps

cmaps = get_project_colormaps()
# Returns:
# {
#     'diverging': 'RdYlGn_r',          # Percent changes (red bad, green good)
#     'diverging_temp': 'RdYlBu_r',     # Temperature (red hot, blue cool)
#     'sequential': 'viridis',           # Continuous data
#     'sequential_light': 'YlOrRd',      # Risk/stress metrics
#     'categorical': 'tab10',            # Discrete categories
#     'vegetation': 'YlGn',              # Vegetation coverage
# }
```

### Scenario Color Gradient

```python
from plot_formatting import create_scenario_colormap

# Get color list for 25 scenarios (gradient from red to green)
colors = create_scenario_colormap(n_scenarios=25)

# Use in scatter plot
for i, (x, y) in enumerate(data):
    ax.scatter(x, y, color=colors[i], s=50)
```

---

## Specialized Functions

### Heatmap Formatting

```python
from plot_formatting import format_heatmap
import numpy as np

fig, ax = plt.subplots(figsize=(8, 6))
data = np.random.randn(5, 5) * 10

ax_formatted, im = format_heatmap(
    ax,
    data,
    xlabel='Landscape Ratio',
    ylabel='Facade Ratio',
    title='Percent Change Heatmap',
    cbar_label='% Change',
    center_zero=True,      # Center colormap on zero
    cmap='RdYlGn_r',       # Red-Yellow-Green reversed
    annotate=True,         # Add value labels
    fmt='.1f'             # Format: 1 decimal place
)

# Add colorbar
cbar = plt.colorbar(im, ax=ax, label='% Change')
```

**Features:**
- Automatic text color selection (white on dark, black on light)
- Centered colormaps for diverging data
- Customizable annotation format
- Returns both axis and image for colorbar creation

### Comparison Plot Formatting

```python
from plot_formatting import format_comparison_plot

fig, ax = plt.subplots(figsize=(10, 6))
ax.bar(scenarios, percent_changes, color=['red' if x > 0 else 'green' for x in percent_changes])

format_comparison_plot(
    ax,
    xlabel='Scenario',
    ylabel='% Change vs Middle Scenario',
    title='Risk Index Changes',
    show_zero_line=True    # Adds horizontal line at y=0
)
```

### Figure Creation Helper

```python
from plot_formatting import create_figure

# Create figure with automatic styling
fig, axes = create_figure(
    nrows=2,
    ncols=2,
    figsize=(12, 10),
    style='presentation',
    sharex=True,
    sharey=False
)

# axes is a 2x2 array
for i, ax in enumerate(axes.flat):
    ax.plot(x, y[i])
    format_plot(ax, title=f'Subplot {i+1}')
```

---

## Integration with run_analysis.py

### Example: Update Heatmap Generation

**Before:**
```python
fig, ax = plt.subplots(figsize=(8, 7))
ax.imshow(pivot_data.values, cmap='RdYlGn_r', vmin=vmin, vmax=vmax)
# ... manual formatting ...
ax.set_title('Percent Change in Tree Risk Index\n(Relative to Middle Scenario 50%/50%)')
```

**After:**
```python
from plot_formatting import format_heatmap, set_project_style

set_project_style('paper')  # For publication quality

fig, ax = plt.subplots(figsize=(8, 7))
ax_formatted, im = format_heatmap(
    ax,
    pivot_data.values,
    xlabel='Landscape Vegetation Ratio',
    ylabel='Facade Vegetation Ratio',
    title='Percent Change in Tree Risk Index\n(Relative to Middle Scenario 50%/50%)',
    center_zero=True,
    annotate=True,
    fmt='.1f'
)
plt.colorbar(im, ax=ax, label='% Change in Weighted Risk Index')
```

### Example: Update Line Plots

**Before:**
```python
fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(x, y, 'r-', linewidth=2)
ax.set_xlabel('X')
ax.set_ylabel('Y')
ax.grid(True, alpha=0.3)
```

**After:**
```python
from plot_formatting import format_plot, get_project_colors

fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(x, y, color=get_project_colors('primary_red'), linewidth=2, label='Data')

format_plot(
    ax,
    xlabel='X Axis',
    ylabel='Y Axis',
    title='Analysis Results',
    legend=True,
    grid=True
)
```

### Example: Batch Update All Plots in Section 5

```python
def generate_plots(pct_df, sensitivity_df, master_summary):
    """Generate publication-quality plots."""
    from plot_formatting import (
        format_plot, format_heatmap, format_comparison_plot,
        set_project_style, get_project_colors
    )
    
    # Set style for all plots
    set_project_style('paper')  # or 'default', 'presentation'
    
    plots_dir = os.path.join(OUTPUT_DIR, 'plots')
    
    # Plot 1: Heatmap
    fig, ax = plt.subplots(figsize=(8, 7))
    pivot_data = pct_df.pivot(...)
    
    ax_fmt, im = format_heatmap(
        ax, pivot_data.values,
        xlabel='Landscape Vegetation Ratio',
        ylabel='Facade Vegetation Ratio',
        title='Percent Change in Tree Risk Index\n(Relative to Middle Scenario 50%/50%)',
        center_zero=True,
        annotate=True
    )
    plt.colorbar(im, ax=ax, label='% Change')
    plt.savefig(os.path.join(plots_dir, 'pct_change_heatmap.png'))
    plt.close()
    
    # Plot 2: Scatter with regression
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    for i, (ax, metric) in enumerate(zip(axes, ['mean_albedo', 'mean_emissivity'])):
        ax.scatter(valid[metric], valid['degree_hours_pct_change'],
                   c=valid['landscape_ratio'], 
                   cmap='viridis', s=80, edgecolor='black', alpha=0.7)
        
        format_comparison_plot(
            ax,
            xlabel=f'{metric.replace("_", " ").title()}',
            ylabel='% Change in Risk Index',
            title=f'Risk vs {metric.split("_")[1].title()}',
            show_zero_line=True
        )
    
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, 'sensitivity_curves.png'))
    plt.close()
```

---

## Complete Example: Custom Analysis Plot

```python
from plot_formatting import (
    format_plot, 
    set_project_style, 
    get_project_colors,
    create_scenario_colormap
)
import matplotlib.pyplot as plt
import numpy as np

# Set style
set_project_style('default')

# Create data
scenarios = [f'S{i:03d}' for i in range(25)]
risk_changes = np.random.randn(25) * 10
landscape_ratios = np.repeat([0, 0.25, 0.5, 0.75, 1.0], 5)

# Create figure
fig, ax = plt.subplots(figsize=(12, 6))

# Plot bars with scenario colors
colors = create_scenario_colormap(25)
bars = ax.bar(range(25), risk_changes, color=colors, edgecolor='black', linewidth=0.5)

# Format plot
format_plot(
    ax,
    xlabel='Scenario',
    ylabel='% Change in Risk Index',
    title='Risk Changes Relative to Middle Scenario (50%/50%)',
    xticks=range(0, 25, 5),
    xticklabels=[scenarios[i] for i in range(0, 25, 5)],
    grid=True,
    grid_which='major',
    show_zero_line=True
)

# Add zero reference line
ax.axhline(y=0, color='black', linewidth=1.0, alpha=0.5, zorder=0)

# Highlight middle scenario
ax.axvline(x=12, color=get_project_colors('middle'), 
           linewidth=2, linestyle='--', alpha=0.7, label='Middle Scenario')

# Add legend
ax.legend(frameon=True, facecolor='white', edgecolor='grey', framealpha=0.9)

plt.tight_layout()
plt.savefig('custom_analysis_plot.png', dpi=300, bbox_inches='tight')
plt.show()
```

---

## Advanced Customization

### Override Specific Parameters

```python
format_plot(
    ax,
    # ... standard parameters ...
    
    # Grid customization
    grid=True,
    grid_which='both',         # 'major', 'minor', or 'both'
    grid_alpha=0.5,            # More opaque grid
    grid_color='#CCCCCC',      # Custom color
    grid_linewidth=0.8,        # Thicker grid lines
    
    # Tick customization
    tick_direction='inout',    # 'in', 'out', or 'inout'
    tick_length=6.0,           # Longer ticks
    tick_width=1.2,            # Thicker ticks
    
    # Spine customization
    show_top_spine=True,       # Show all spines
    show_right_spine=True,
    spine_linewidth=1.5,       # Thicker frame
    spine_color='#333333',     # Dark grey frame
    
    # Font customization
    label_fontsize=14,
    title_fontsize=16,
    tick_fontsize=11,
    
    # Legend customization
    legend=True,
    legend_loc='upper right',
    legend_frameon=True,
    legend_fontsize=10
)
```

### Manual Style Override

```python
import matplotlib.pyplot as plt

# Set project style first
set_project_style('default')

# Then override specific rcParams
plt.rcParams.update({
    'axes.grid': False,           # Turn off grid
    'font.family': 'serif',       # Use serif font
    'axes.facecolor': '#F5F5F5',  # Light grey background
})
```

---

## Tips and Best Practices

1. **Set style once at the beginning**: Call `set_project_style()` at the start of your script
2. **Use format_plot() consistently**: Apply to all axes for uniform appearance
3. **Save with high DPI**: Use `dpi=300` or higher for publications
4. **Choose appropriate colormaps**: 
   - Diverging (RdYlGn_r) for percent changes
   - Sequential (viridis) for continuous increasing data
   - Avoid rainbow colormaps (jet) - they're not perceptually uniform
5. **Annotate heatmaps**: Makes values immediately readable
6. **Use project colors**: Maintains consistent branding across figures

---

## Troubleshooting

### Grid not showing
```python
# Make sure grid is True and behind data
format_plot(ax, grid=True)
ax.set_axisbelow(True)  # Explicit setting
```

### Text too small in saved figure
```python
# Use larger DPI or presentation style
set_project_style('presentation')
plt.savefig('plot.png', dpi=300)
```

### Legend overlapping data
```python
# Try different locations or place outside plot
format_plot(ax, legend=True, legend_loc='upper left')
# Or manually:
ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
```

### Tight layout warnings
```python
# Disable tight layout in format_plot
format_plot(ax, tight=False)
# Then manually call:
plt.tight_layout()
```

---

## Version History

- **v1.0** (2026-01-12): Initial release
  - Core formatting functions
  - Four style presets
  - 18 project colors
  - Specialized heatmap and comparison plot formatting
