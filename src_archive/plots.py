"""
Plotting functions for JODLA project analysis.

Provides reusable, publication-quality plotting functions that use
the project's standardized formatting from plot_formatting.py.

Usage:
    import plots
    import run_analysis
    
    sensitivity_df = run_analysis.run_sensitivity_analysis(pct_df)
    fig = plots.plot_sensitivity_by_surface_type(sensitivity_df)
"""

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import numpy as np
import pandas as pd
from typing import Optional, Tuple
import os

try:
    import plot_formatting as pf
except ImportError:
    pf = None



def plot_sensitivity_by_surface_type(
    sensitivity_df: pd.DataFrame,
    output_path: Optional[str] = None,
    figsize: Tuple[float, float] = (16, 4),
    cmap: str = 'BrBG'
) -> plt.Figure:
    """
    Generate 4-panel sensitivity plot separating landscape and facade surfaces.
    
    Creates a figure with columns:
    - Risk vs Landscape Albedo (colored by landscape vegetation ratio)
    - Risk vs Landscape Emissivity (colored by landscape vegetation ratio)
    - Risk vs Facade Albedo (colored by facade vegetation ratio)
    - Risk vs Facade Emissivity (colored by facade vegetation ratio)
    
    Args:
        sensitivity_df: DataFrame from run_sensitivity_analysis() with columns:
            - landscape_albedo, landscape_emissivity
            - facade_albedo, facade_emissivity
            - landscape_ratio, facade_ratio
            - degree_hours_pct_change
            And attrs['regression'] containing regression results.
        output_path: Optional path to save figure. If None, figure is not saved.
        figsize: Figure size as (width, height) tuple.
        cmap: Colormap name for scatter points.
        
    Returns:
        matplotlib Figure object
    """
    fig, axes = plt.subplots(1, 4, figsize=figsize, sharey=True)
    
    # Get regression results if available
    regression = sensitivity_df.attrs.get('regression', {})
    
    # Define plot configurations
    plot_configs = [
        {
            'ax_idx': 0,
            'x_col': 'landscape_albedo',
            'color_col': 'landscape_ratio',
            'reg_key': 'risk_landscape_albedo',
            'xlabel': 'Landscape Albedo',
            'title': 'Risk vs Landscape Albedo',
            'cbar_label': 'Landscape Veg. Ratio'
        },
        {
            'ax_idx': 1,
            'x_col': 'landscape_emissivity',
            'color_col': 'landscape_ratio',
            'reg_key': 'risk_landscape_emissivity',
            'xlabel': 'Landscape Emissivity',
            'title': 'Risk vs Landscape Emissivity',
            'cbar_label': 'Landscape Veg. Ratio'
        },
        {
            'ax_idx': 2,
            'x_col': 'facade_albedo',
            'color_col': 'facade_ratio',
            'reg_key': 'risk_facade_albedo',
            'xlabel': 'Facade Albedo',
            'title': 'Risk vs Facade Albedo',
            'cbar_label': 'Facade Veg. Ratio'
        },
        {
            'ax_idx': 3,
            'x_col': 'facade_emissivity',
            'color_col': 'facade_ratio',
            'reg_key': 'risk_facade_emissivity',
            'xlabel': 'Facade Emissivity',
            'title': 'Risk vs Facade Emissivity',
            'cbar_label': 'Facade Veg. Ratio'
        }
    ]
    
    for config in plot_configs:
        ax = axes[config['ax_idx']]
        
        # Filter valid data
        valid = sensitivity_df.dropna(subset=[config['x_col'], 'degree_hours_pct_change'])
        
        if len(valid) == 0:
            ax.text(0.5, 0.5, 'No data available', ha='center', va='center',
                   transform=ax.transAxes)
            ax.set_title(config['title'])
            continue
        
        # Create scatter plot
        scatter = ax.scatter(
            valid[config['x_col']], 
            valid['degree_hours_pct_change'],
            c=valid[config['color_col']], 
            cmap=cmap, 
            s=80, 
            edgecolor='black', 
            alpha=0.7,
            vmin=0, vmax=1
        )
        
        # Add regression line if available
        reg = regression.get(config['reg_key'])
        if reg:
            x_line = np.linspace(valid[config['x_col']].min(), 
                                valid[config['x_col']].max(), 100)
            y_line = reg['slope'] * x_line + reg['intercept']
            ax.plot(x_line, y_line, 'r--', linewidth=2,
                   label=f"y = {reg['slope']:.1f}x + {reg['intercept']:.1f}\nR² = {reg['r2']:.3f}")
            ax.legend(loc='best', fontsize=8)
        
        # Add zero line
        ax.axhline(y=0, color='gray', linestyle='-', alpha=0.5)
        
        # Labels and title
        ax.set_xlabel(config['xlabel'])
        ax.set_title(config['title'])
        
        # Add colorbar for this panel
        cbar = fig.colorbar(scatter, ax=ax, shrink=0.8, pad=0.02)
        cbar.set_label(config['cbar_label'], fontsize=8)
    
    # Set shared y-axis label
    axes[0].set_ylabel('% Change in Risk Index')
    
    # Apply project formatting if available
    if pf is not None:
        for ax in axes:
            pf.format_plot(ax)
    
    plt.tight_layout()
    
    # Save if output path provided
    if output_path:
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', 
                   exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"   Saved: {output_path}")
    
    return fig


def plot_combined_sensitivity(
    sensitivity_df: pd.DataFrame,
    output_path: Optional[str] = None,
    figsize: Tuple[float, float] = (12, 5),
    cmap: str = 'BrBG'
) -> plt.Figure:
    """
    Generate 2-panel combined sensitivity plot (original style).
    
    Creates a figure with:
    - Risk vs Combined Mean Albedo (colored by landscape vegetation ratio)
    - Risk vs Combined Mean Emissivity (colored by landscape vegetation ratio)
    
    Args:
        sensitivity_df: DataFrame from run_sensitivity_analysis()
        output_path: Optional path to save figure.
        figsize: Figure size as (width, height) tuple.
        cmap: Colormap name for scatter points.
        
    Returns:
        matplotlib Figure object
    """
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    
    regression = sensitivity_df.attrs.get('regression', {})
    valid = sensitivity_df.dropna(subset=['mean_albedo', 'degree_hours_pct_change'])
    
    # Risk vs Albedo
    ax = axes[0]
    scatter = ax.scatter(
        valid['mean_albedo'], 
        valid['degree_hours_pct_change'],
        c=valid['landscape_ratio'], 
        cmap=cmap, 
        s=80, 
        edgecolor='black', 
        alpha=0.7
    )
    fig.colorbar(scatter, ax=ax, label='Landscape Vegetation Ratio')
    
    reg = regression.get('risk_albedo')
    if reg:
        x_line = np.linspace(valid['mean_albedo'].min(), valid['mean_albedo'].max(), 100)
        y_line = reg['slope'] * x_line + reg['intercept']
        ax.plot(x_line, y_line, 'r--', linewidth=2,
               label=f"y = {reg['slope']:.1f}x + {reg['intercept']:.1f}\nR² = {reg['r2']:.3f}")
        ax.legend(loc='best')
    
    ax.axhline(y=0, color='gray', linestyle='-', alpha=0.5)
    ax.set_xlabel('Area-Weighted Mean Albedo')
    ax.set_ylabel('% Change in Risk Index')
    ax.set_title('Risk Sensitivity to Surface Albedo')
    
    # Risk vs Emissivity
    ax = axes[1]
    scatter = ax.scatter(
        valid['mean_emissivity'], 
        valid['degree_hours_pct_change'],
        c=valid['landscape_ratio'], 
        cmap=cmap, 
        s=80, 
        edgecolor='black', 
        alpha=0.7
    )
    fig.colorbar(scatter, ax=ax, label='Landscape Vegetation Ratio')
    
    reg = regression.get('risk_emissivity')
    if reg:
        x_line = np.linspace(valid['mean_emissivity'].min(), valid['mean_emissivity'].max(), 100)
        y_line = reg['slope'] * x_line + reg['intercept']
        ax.plot(x_line, y_line, 'r--', linewidth=2,
               label=f"y = {reg['slope']:.1f}x + {reg['intercept']:.1f}\nR² = {reg['r2']:.3f}")
        ax.legend(loc='best')
    
    ax.axhline(y=0, color='gray', linestyle='-', alpha=0.5)
    ax.set_xlabel('Area-Weighted Mean Emissivity')
    ax.set_ylabel('% Change in Risk Index')
    ax.set_title('Risk Sensitivity to Surface Emissivity')
    
    # Apply project formatting if available
    if pf is not None:
        for ax in axes:
            pf.format_plot(ax)
    
    plt.tight_layout()
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', 
                   exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"   Saved: {output_path}")
    
    return fig


def plot_risk_heatmap(
    pct_df: pd.DataFrame,
    output_path: Optional[str] = None,
    figsize: Tuple[float, float] = (8, 7),
    cmap: str = 'RdYlGn_r'
) -> plt.Figure:
    """
    Generate heatmap of risk percent change across scenario grid.
    
    Args:
        pct_df: DataFrame with columns: landscape_ratio, facade_ratio, degree_hours_pct_change
        output_path: Optional path to save figure.
        figsize: Figure size as (width, height) tuple.
        cmap: Colormap name (diverging recommended).
        
    Returns:
        matplotlib Figure object
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    # Create pivot table for heatmap
    pivot_data = pct_df.pivot(
        index='facade_ratio',
        columns='landscape_ratio',
        values='degree_hours_pct_change'
    )
    
    # Determine color scale centered on zero
    vmax = max(abs(pivot_data.min().min()), abs(pivot_data.max().max()))
    vmin = -vmax
    
    im = ax.imshow(pivot_data.values, cmap=cmap, vmin=vmin, vmax=vmax, aspect='equal')
    
    # Add colorbar
    plt.colorbar(im, ax=ax, label='% Change in Weighted Risk Index')
    
    # Add annotations
    for i in range(len(pivot_data.index)):
        for j in range(len(pivot_data.columns)):
            val = pivot_data.values[i, j]
            color = 'white' if abs(val) > vmax*0.5 else 'black'
            ax.text(j, i, f'{val:.1f}%', ha='center', va='center', color=color, fontsize=10)
    
    ax.set_xticks(range(len(pivot_data.columns)))
    ax.set_xticklabels([f'{x:.0%}' for x in pivot_data.columns])
    ax.set_yticks(range(len(pivot_data.index)))
    ax.set_yticklabels([f'{y:.0%}' for y in pivot_data.index])
    ax.set_xlabel('Landscape Vegetation Ratio')
    ax.set_ylabel('Facade Vegetation Ratio')
    ax.set_title('Percent Change in Tree Risk Index\n(Relative to Middle Scenario 50%/50%)')
    
    plt.tight_layout()
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', 
                   exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"   Saved: {output_path}")
    
    return fig


def plot_scenario_concept(
    sensitivity_df: pd.DataFrame,
    output_path: Optional[str] = None,
    figsize: Tuple[float, float] = (8, 6)
) -> plt.Figure:
    """
    Generate scenario concept diagram showing albedo (color) and emissivity (size).
    
    Creates a grid visualization of all scenarios with:
    - X-axis: Landscape vegetation ratio
    - Y-axis: Facade vegetation ratio
    - Color: Mean albedo (darker = lower albedo)
    - Size: Mean emissivity (larger = higher emissivity)
    
    Args:
        sensitivity_df: DataFrame with columns: landscape_ratio, facade_ratio, 
                        mean_albedo, mean_emissivity
        output_path: Optional path to save figure.
        figsize: Figure size as (width, height) tuple.
        
    Returns:
        matplotlib Figure object
    """
    # Create scenario grid
    predefined_scenarios = []
    for x in np.arange(0, 1.1, 0.25):
        for y in np.arange(0, 1.1, 0.25):
            predefined_scenarios.append((x, y))
    
    plot_df = pd.DataFrame(predefined_scenarios, columns=['landscape_ratio', 'facade_ratio'])
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Draw quadrant axes
    ax.vlines(0.5, -0.1, 1.1, color='black', zorder=10)
    ax.hlines(0.5, -0.1, 1.1, color='black', zorder=10)
    
    # Get material properties
    albedo_values = sensitivity_df['mean_albedo'].values
    emissivity_values = sensitivity_df['mean_emissivity'].values
    
    # Normalize emissivity to point sizes
    size_min, size_max = 10, 500
    emissivity_min, emissivity_max = emissivity_values.min(), emissivity_values.max()
    sizes = size_min + (emissivity_values - emissivity_min) / (emissivity_max - emissivity_min) * (size_max - size_min)
    
    # Create scatter plot
    scatter = ax.scatter(
        plot_df['landscape_ratio'], 
        plot_df['facade_ratio'], 
        c=albedo_values, 
        s=sizes, 
        vmin=0, vmax=0.6,
        cmap='binary_r', 
        ec='none', 
        marker='o', 
        zorder=100
    )
    
    # Add colorbar for albedo
    axins = inset_axes(
        ax,
        width="5%",
        height="60%",
        loc='right',
        bbox_to_anchor=(0.47, 0, 0.8, 0.8),
        bbox_transform=ax.transAxes,
        borderpad=0,
    )
    fig.colorbar(scatter, cax=axins, orientation='vertical', label='Mean Albedo')
    
    # Labels
    ax.set_xlabel('Landscape Vegetation Ratio')
    ax.set_ylabel('Facade Vegetation Ratio')
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    ax.set_xticks(np.arange(0, 1.01, 0.25))
    ax.set_yticks(np.arange(0, 1.01, 0.25))
    
    # Add text labels to each point
    inc = 0.025
    for i, row in plot_df.iterrows():
        ax.text(
            row['landscape_ratio'] + inc, 
            row['facade_ratio'] + inc,
            f'Scenario {str(i).zfill(2)}\nAlbedo: {albedo_values[i]:.2f}\nEmissivity: {emissivity_values[i]:.2f}',
            fontsize=9, ha='left', va='bottom'
        )
    
    # Remove frame and ticks
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.tick_params(top=False, right=False, bottom=False, left=False)
    ax.grid(True, alpha=0.5, which='major')
    
    # Create size legend for emissivity
    legend_emissivity = [
        emissivity_min,
        emissivity_min + (emissivity_max - emissivity_min) * 0.25,
        emissivity_min + (emissivity_max - emissivity_min) * 0.75,
        emissivity_max
    ]
    legend_sizes = [
        size_min + (e - emissivity_min) / (emissivity_max - emissivity_min) * (size_max - size_min)
        for e in legend_emissivity
    ]
    
    legend_handles = [plt.scatter([], [], s=s, c='grey', ec='none', marker='o') 
                      for s in legend_sizes]
    legend_labels = [f'{e:.2f}' for e in legend_emissivity]
    
    ax.legend(
        legend_handles, legend_labels,
        title='Emissivity', loc='upper right',
        frameon=True, facecolor='white', edgecolor='k',
        framealpha=1, labelspacing=2,
        borderpad=1.1,
        bbox_to_anchor=(0.4, 0.07, 0.96, 0.96)
    )
    
    plt.tight_layout()
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', 
                   exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"   Saved: {output_path}")
    
    return fig


def plot_leaf_temp_uncertainty(
    leaf_temp_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    output_path: Optional[str] = None,
    figsize: Tuple[float, float] = (12, 6)
) -> plt.Figure:
    """
    Generate leaf temperature uncertainty plot with weather overlays.
    
    Creates a figure with:
    - GHI background patches (cividis colormap)
    - Leaf temperature uncertainty band (min/max fill, median line)
    - Air temperature on secondary y-axis
    - Relative humidity on extended secondary y-axis
    - Horizontal GHI colorbar below x-axis
    
    Args:
        leaf_temp_df: DataFrame with datetime index and scenario columns containing
                      leaf temperatures. Each column is a different scenario.
        weather_df: DataFrame with columns: K_down (GHI), Ta (air temp), RH (relative humidity)
                    Should have same length as leaf_temp_df.
        output_path: Optional path to save figure.
        figsize: Figure size as (width, height) tuple.
        
    Returns:
        matplotlib Figure object
    """
    # Apply project style if available
    if pf is not None:
        pf.set_project_style(style='paper')
    
    fig, ax1 = plt.subplots(figsize=figsize)
    
    # Add GHI background patches using cividis colormap
    ghi_values = weather_df['K_down'].values
    ghi_norm = mcolors.Normalize(vmin=0, vmax=ghi_values.max())
    cmap = plt.cm.cividis
    
    # Create background patches for each hour based on GHI
    for i in range(len(leaf_temp_df.index) - 1):
        color = cmap(ghi_norm(ghi_values[i]))
        ax1.axvspan(leaf_temp_df.index[i], leaf_temp_df.index[i+1],
                   facecolor=color, alpha=0.3, zorder=0, linewidth=0)
    
    # Handle the last time point
    if len(leaf_temp_df.index) > 0:
        color = cmap(ghi_norm(ghi_values[-1]))
        time_delta = leaf_temp_df.index[1] - leaf_temp_df.index[0] if len(leaf_temp_df.index) > 1 else pd.Timedelta(hours=1)
        ax1.axvspan(leaf_temp_df.index[-1], leaf_temp_df.index[-1] + time_delta,
                   facecolor=color, alpha=0.3, zorder=0, linewidth=0)
    
    # Calculate statistics across all scenarios
    leaf_median = leaf_temp_df.median(axis=1)
    leaf_min = leaf_temp_df.min(axis=1)
    leaf_max = leaf_temp_df.max(axis=1)
    
    # Plot leaf temperature uncertainty band
    ax1.fill_between(
        leaf_temp_df.index,
        leaf_min,
        leaf_max,
        color='#AED6F1',  # Light blue fill
        alpha=0.4,
        label='Leaf Temp Range',
        zorder=2
    )
    ax1.plot(leaf_temp_df.index, leaf_min, color='#1F618D', linewidth=1, alpha=0.8, zorder=3)
    ax1.plot(leaf_temp_df.index, leaf_max, color='#1F618D', linewidth=1, alpha=0.8, zorder=3)
    ax1.plot(leaf_temp_df.index, leaf_median, color='#E74C3C', linewidth=0.5, 
             label='Leaf Temp Median', zorder=4)
    
    # Format primary y-axis
    if pf is not None:
        pf.format_plot(ax1, ylabel='Leaf Temperature (°C)', ylim=(10, 35), legend=False)
    ax1.set_ylabel('Leaf Temperature (°C)', color='#1F618D', fontsize=12, fontweight='bold')
    ax1.tick_params(axis='y', labelcolor='#1F618D')
    
    # Secondary y-axis for air temperature
    ax2 = ax1.twinx()
    ax2.plot(leaf_temp_df.index, weather_df['Ta'].values, color='black', linewidth=1.5,
             label='Air Temperature', linestyle='-')
    ax2.set_ylabel('Air Temperature (°C)', color='black', fontsize=12, fontweight='bold')
    ax2.tick_params(axis='y', labelcolor='black')
    ax2.set_ylim(10, 35)
    
    # Third y-axis for relative humidity
    ax3 = ax1.twinx()
    ax3.spines['right'].set_position(('outward', 60))
    ax3.plot(leaf_temp_df.index, weather_df['RH'].values, color='#7F8C8D', linewidth=1.5,
             label='Relative Humidity', linestyle='--')
    ax3.set_ylabel('Relative Humidity (%)', color='#7F8C8D', fontsize=12, fontweight='bold')
    ax3.tick_params(axis='y', labelcolor='#7F8C8D')
    ax3.set_ylim(0, 100)
    
    # Create legends
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    lines3, labels3 = ax3.get_legend_handles_labels()
    
    ax1.legend(lines1, labels1, loc='lower left', frameon=True, facecolor='white',
               edgecolor='k', framealpha=1, fontsize=10)
    ax2.legend(lines2 + lines3, labels2 + labels3, loc='lower right', frameon=True,
               facecolor='white', edgecolor='k', framealpha=1, fontsize=10)
    
    # Add horizontal colorbar for GHI below x-axis
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=ghi_norm)
    sm.set_array([])
    
    cbar_ax = fig.add_axes([0.125, 0.05, 0.775, 0.02])
    cbar = fig.colorbar(sm, cax=cbar_ax, orientation='horizontal')
    cbar.set_label('Global Horizontal Irradiance (W/m²)', fontsize=10)
    cbar.ax.tick_params(labelsize=9)
    
    plt.subplots_adjust(bottom=0.12)
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', 
                   exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"   Saved: {output_path}")
    
    return fig


def plot_material_properties_comparison(
    material_db_path: str = 'root_material_database.csv',
    output_path: Optional[str] = None,
    figsize: Tuple[float, float] = (12, 8)
) -> plt.Figure:
    """
    Generate bar chart comparison of albedo and emissivity for landscape vs facade materials.
    
    Creates a 2x2 panel figure:
    - Top row: Landscape materials (albedo, emissivity)
    - Bottom row: Facade materials (albedo, emissivity)
    
    Bar colors indicate naturalness score (green=natural, red=artificial).
    
    Args:
        material_db_path: Path to the root material database CSV
        output_path: Optional path to save figure.
        figsize: Figure size as (width, height) tuple.
        
    Returns:
        matplotlib Figure object
    """
    # Load material database
    material_db = pd.read_csv(material_db_path)
    
    # Filter by surface type applicability
    landscape_materials = material_db[material_db['ground_applicable'] == True].copy()
    facade_materials = material_db[material_db['facade_applicable'] == True].copy()
    
    # Sort by naturalness score (highest at top)
    landscape_materials = landscape_materials.sort_values('naturalness_score', ascending=False)
    facade_materials = facade_materials.sort_values('naturalness_score', ascending=False)
    
    # Create figure
    fig, axes = plt.subplots(2, 2, figsize=figsize)
    
    # Colors based on naturalness (green=natural, brown=artificial)
    def get_colors(df):
        cmap = plt.cm.RdYlGn
        return [cmap(score) for score in df['naturalness_score'].values]
    
    bar_height = 0.6
    
    # --- Top Left: Landscape Albedo ---
    ax = axes[0, 0]
    positions = np.arange(len(landscape_materials))
    colors = get_colors(landscape_materials)
    
    ax.barh(positions, landscape_materials['shortwave_albedo'].values,
            height=bar_height, color=colors, edgecolor='black', linewidth=0.5)
    
    for i, (_, row) in enumerate(landscape_materials.iterrows()):
        ax.text(row['shortwave_albedo'] + 0.02, i, f"{row['shortwave_albedo']:.2f}",
                va='center', ha='left', fontsize=9)
    
    ax.set_yticks(positions)
    ax.set_yticklabels(landscape_materials['material_name'].str.replace('_', ' ').str.title())
    ax.set_xlabel('Shortwave Albedo')
    ax.set_title('Landscape Materials - Albedo', fontweight='bold', color='#27AE60')
    ax.set_xlim(0, 0.85)
    ax.invert_yaxis()
    
    # --- Top Right: Landscape Emissivity ---
    ax = axes[0, 1]
    
    ax.barh(positions, landscape_materials['thermal_emissivity'].values,
            height=bar_height, color=colors, edgecolor='black', linewidth=0.5)
    
    for i, (_, row) in enumerate(landscape_materials.iterrows()):
        ax.text(row['thermal_emissivity'] + 0.003, i, f"{row['thermal_emissivity']:.2f}",
                va='center', ha='left', fontsize=9)
    
    ax.set_yticks(positions)
    ax.set_yticklabels([])  # Hide labels on right side
    ax.set_xlabel('Thermal Emissivity')
    ax.set_title('Landscape Materials - Emissivity', fontweight='bold', color='#27AE60')
    ax.set_xlim(0.82, 1.0)
    ax.invert_yaxis()
    
    # --- Bottom Left: Facade Albedo ---
    ax = axes[1, 0]
    positions = np.arange(len(facade_materials))
    colors = get_colors(facade_materials)
    
    ax.barh(positions, facade_materials['shortwave_albedo'].values,
            height=bar_height, color=colors, edgecolor='black', linewidth=0.5)
    
    for i, (_, row) in enumerate(facade_materials.iterrows()):
        ax.text(row['shortwave_albedo'] + 0.02, i, f"{row['shortwave_albedo']:.2f}",
                va='center', ha='left', fontsize=9)
    
    ax.set_yticks(positions)
    ax.set_yticklabels(facade_materials['material_name'].str.replace('_', ' ').str.title())
    ax.set_xlabel('Shortwave Albedo')
    ax.set_title('Facade Materials - Albedo', fontweight='bold', color='#3498DB')
    ax.set_xlim(0, 0.85)
    ax.invert_yaxis()
    
    # --- Bottom Right: Facade Emissivity ---
    ax = axes[1, 1]
    
    ax.barh(positions, facade_materials['thermal_emissivity'].values,
            height=bar_height, color=colors, edgecolor='black', linewidth=0.5)
    
    for i, (_, row) in enumerate(facade_materials.iterrows()):
        ax.text(row['thermal_emissivity'] + 0.003, i, f"{row['thermal_emissivity']:.2f}",
                va='center', ha='left', fontsize=9)
    
    ax.set_yticks(positions)
    ax.set_yticklabels([])
    ax.set_xlabel('Thermal Emissivity')
    ax.set_title('Facade Materials - Emissivity', fontweight='bold', color='#3498DB')
    ax.set_xlim(0.82, 1.0)
    ax.invert_yaxis()
    
    # Add note about color meaning
    fig.text(0.5, 0.01, 
             'Bar colors indicate naturalness: Green = Natural/Vegetated, Yellow = Moderate, Red = Artificial/Impervious',
             ha='center', fontsize=10, style='italic')
    
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.08)
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.',
                   exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"   Saved: {output_path}")
    
    return fig
