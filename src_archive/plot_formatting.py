"""
Plot Formatting Module for JODLA Project

Provides standardized, publication-quality plot formatting with a minimalist aesthetic.
Default style: clean appearance with inward ticks and light grey grid.

Usage:
    from plot_formatting import format_plot, get_project_colors, get_project_colormaps
    
    fig, ax = plt.subplots()
    ax.plot(x, y)
    format_plot(ax, xlabel='X Label', ylabel='Y Label', title='My Plot')
"""

import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import rcParams
import numpy as np
from typing import Optional, Union, Tuple, List, Dict


# =============================================================================
# PROJECT COLOR SCHEMES
# =============================================================================

PROJECT_COLORS = {
    # Primary colors
    'primary_blue': '#2E5C8A',
    'primary_green': '#2D8659',
    'primary_red': '#C44E4E',
    'primary_yellow': '#D4A942',
    'primary_purple': '#7B5F9E',
    
    # Scenario colors
    'low_vegetation': '#E74C3C',      # Red for low vegetation (0%)
    'mid_low': '#F39C12',             # Orange
    'middle': '#F1C40F',              # Yellow for middle (50%)
    'mid_high': '#2ECC71',            # Light green
    'high_vegetation': '#27AE60',     # Green for high vegetation (100%)
    
    # Neutral colors
    'dark_grey': '#2C3E50',
    'medium_grey': '#7F8C8D',
    'light_grey': '#BDC3C7',
    'very_light_grey': '#ECF0F1',
    'white': '#FFFFFF',
    
    # Heatmap extremes
    'cool': '#3498DB',
    'neutral': '#F5F5F5',
    'warm': '#E74C3C',
}


def get_project_colors(name: Optional[str] = None) -> Union[str, Dict[str, str]]:
    """
    Get project color scheme.
    
    Args:
        name: Specific color name, or None to return all colors
        
    Returns:
        Color hex code or dictionary of all colors
    """
    if name is None:
        return PROJECT_COLORS.copy()
    return PROJECT_COLORS.get(name, '#000000')


def get_project_colormaps() -> Dict[str, str]:
    """
    Get recommended matplotlib colormaps for different plot types.
    
    Returns:
        Dictionary mapping plot types to colormap names
    """
    return {
        'diverging': 'RdYlGn_r',      # For percent changes (red bad, green good)
        'diverging_temp': 'RdYlBu_r',  # For temperature changes (red hot, blue cool)
        'sequential': 'viridis',       # For continuous data
        'sequential_light': 'YlOrRd',  # For risk/stress metrics
        'categorical': 'tab10',        # For discrete categories
        'vegetation': 'YlGn',          # For vegetation coverage
    }


# =============================================================================
# MAIN FORMATTING FUNCTION
# =============================================================================

def format_plot(
    ax: plt.Axes,
    # Labels and titles
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None,
    title: Optional[str] = None,
    
    # Limits
    xlim: Optional[Tuple[float, float]] = None,
    ylim: Optional[Tuple[float, float]] = None,
    
    # Grid
    grid: bool = True,
    grid_which: str = 'major',
    grid_alpha: float = 0.3,
    grid_color: str = 'lightgrey',
    grid_linewidth: float = 0.5,
    
    # Ticks
    tick_direction: str = 'in',
    tick_length: float = 4.0,
    tick_width: float = 0.8,
    xticks: Optional[List] = None,
    yticks: Optional[List] = None,
    xticklabels: Optional[List] = None,
    yticklabels: Optional[List] = None,
    
    # Spines (frame)
    show_top_spine: bool = False,
    show_right_spine: bool = False,
    spine_linewidth: float = 0.8,
    spine_color: str = 'black',
    
    # Legend
    legend: bool = False,
    legend_loc: str = 'best',
    legend_frameon: bool = False,
    legend_fontsize: Union[str, float] = 'medium',
    
    # Font sizes
    label_fontsize: Union[str, float] = 12,
    title_fontsize: Union[str, float] = 14,
    tick_fontsize: Union[str, float] = 10,
    
    # Aspect ratio and tight layout
    aspect: Optional[str] = None,
    tight: bool = True,
    
    # Additional kwargs
    **kwargs
) -> plt.Axes:
    """
    Apply standardized formatting to a matplotlib axis.
    
    Args:
        ax: Matplotlib axis object to format
        
        Labels and Titles:
            xlabel: X-axis label
            ylabel: Y-axis label  
            title: Plot title
            
        Limits:
            xlim: X-axis limits as (min, max)
            ylim: Y-axis limits as (min, max)
            
        Grid:
            grid: Show grid lines
            grid_which: 'major', 'minor', or 'both'
            grid_alpha: Grid transparency (0-1)
            grid_color: Grid color
            grid_linewidth: Grid line width
            
        Ticks:
            tick_direction: 'in', 'out', or 'inout'
            tick_length: Length of tick marks
            tick_width: Width of tick marks
            xticks: Custom x-tick positions
            yticks: Custom y-tick positions
            xticklabels: Custom x-tick labels
            yticklabels: Custom y-tick labels
            
        Spines (Frame):
            show_top_spine: Show top spine
            show_right_spine: Show right spine
            spine_linewidth: Spine line width
            spine_color: Spine color
            
        Legend:
            legend: Show legend
            legend_loc: Legend location
            legend_frameon: Show legend frame
            legend_fontsize: Legend font size
            
        Font Sizes:
            label_fontsize: Axis label font size
            title_fontsize: Title font size
            tick_fontsize: Tick label font size
            
        Layout:
            aspect: Axis aspect ratio ('equal', 'auto', or float)
            tight: Apply tight_layout
            
    Returns:
        Formatted axis object
    """
    # Set labels
    if xlabel is not None:
        ax.set_xlabel(xlabel, fontsize=label_fontsize)
    if ylabel is not None:
        ax.set_ylabel(ylabel, fontsize=label_fontsize)
    if title is not None:
        ax.set_title(title, fontsize=title_fontsize, pad=10)
    
    # Set limits
    if xlim is not None:
        ax.set_xlim(xlim)
    if ylim is not None:
        ax.set_ylim(ylim)
    
    # Configure grid
    if grid:
        ax.grid(True, which=grid_which, alpha=grid_alpha, 
                color=grid_color, linewidth=grid_linewidth, zorder=0)
    else:
        ax.grid(False)
    
    # Configure ticks
    ax.tick_params(
        axis='both',
        which='both',
        direction=tick_direction,
        length=tick_length,
        width=tick_width,
        labelsize=tick_fontsize,
        top=show_top_spine,
        right=show_right_spine,
    )
    
    # Set custom ticks if provided
    if xticks is not None:
        ax.set_xticks(xticks)
    if yticks is not None:
        ax.set_yticks(yticks)
    if xticklabels is not None:
        ax.set_xticklabels(xticklabels)
    if yticklabels is not None:
        ax.set_yticklabels(yticklabels)
    
    # Configure spines
    ax.spines['top'].set_visible(show_top_spine)
    ax.spines['right'].set_visible(show_right_spine)
    
    for spine_name in ['top', 'right', 'bottom', 'left']:
        spine = ax.spines[spine_name]
        if spine.get_visible():
            spine.set_linewidth(spine_linewidth)
            spine.set_color(spine_color)
    
    # Configure legend
    if legend:
        leg = ax.legend(
            loc=legend_loc,
            frameon=legend_frameon,
            fontsize=legend_fontsize
        )
        if leg and legend_frameon:
            leg.get_frame().set_linewidth(0.5)
            leg.get_frame().set_edgecolor(spine_color)
    
    # Set aspect ratio
    if aspect is not None:
        ax.set_aspect(aspect)
    
    # Apply tight layout
    if tight and ax.figure:
        try:
            ax.figure.tight_layout()
        except Exception:
            pass  # Tight layout can fail in some cases
    
    return ax


# =============================================================================
# STYLE CONTEXT MANAGERS
# =============================================================================

def set_project_style(style: str = 'default'):
    """
    Set global matplotlib style for the project.
    
    Args:
        style: Style preset ('default', 'presentation', 'paper', 'poster')
    """
    # Base style settings
    base_params = {
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
        'font.size': 11,
        
        'axes.linewidth': 0.8,
        'axes.edgecolor': 'black',
        'axes.labelsize': 12,
        'axes.titlesize': 14,
        'axes.titlepad': 10,
        'axes.labelpad': 5,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.grid': True,
        'axes.grid.which': 'major',
        'axes.axisbelow': True,
        
        'grid.alpha': 0.3,
        'grid.color': 'lightgrey',
        'grid.linewidth': 0.5,
        
        'xtick.direction': 'in',
        'ytick.direction': 'in',
        'xtick.major.size': 4,
        'ytick.major.size': 4,
        'xtick.major.width': 0.8,
        'ytick.major.width': 0.8,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        
        'legend.frameon': False,
        'legend.fontsize': 10,
        'legend.loc': 'best',
        
        'figure.facecolor': 'white',
        'figure.edgecolor': 'white',
        'figure.dpi': 100,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.1,
        
        'lines.linewidth': 1.5,
        'lines.markersize': 6,
        
        'image.cmap': 'viridis',
        'image.interpolation': 'nearest',
    }
    
    # Style-specific overrides
    if style == 'presentation':
        base_params.update({
            'font.size': 14,
            'axes.labelsize': 16,
            'axes.titlesize': 18,
            'xtick.labelsize': 12,
            'ytick.labelsize': 12,
            'legend.fontsize': 12,
            'lines.linewidth': 2.0,
            'lines.markersize': 8,
        })
    
    elif style == 'paper':
        base_params.update({
            'font.size': 9,
            'axes.labelsize': 10,
            'axes.titlesize': 11,
            'xtick.labelsize': 8,
            'ytick.labelsize': 8,
            'legend.fontsize': 8,
            'lines.linewidth': 1.0,
            'lines.markersize': 4,
            'savefig.dpi': 600,
        })
    
    elif style == 'poster':
        base_params.update({
            'font.size': 18,
            'axes.labelsize': 22,
            'axes.titlesize': 26,
            'xtick.labelsize': 16,
            'ytick.labelsize': 16,
            'legend.fontsize': 16,
            'lines.linewidth': 3.0,
            'lines.markersize': 12,
            'axes.linewidth': 1.5,
        })
    
    # Apply settings
    plt.rcParams.update(base_params)


class PlotStyle:
    """
    Context manager for temporary plot style changes.
    
    Usage:
        with PlotStyle('presentation'):
            fig, ax = plt.subplots()
            ax.plot(x, y)
            format_plot(ax)
    """
    
    def __init__(self, style: str = 'default'):
        self.style = style
        self.old_params = None
    
    def __enter__(self):
        # Save current rcParams
        self.old_params = rcParams.copy()
        # Apply new style
        set_project_style(self.style)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore old rcParams
        plt.rcParams.update(self.old_params)


# =============================================================================
# SPECIALIZED FORMATTING FUNCTIONS
# =============================================================================

def format_heatmap(
    ax: plt.Axes,
    data: np.ndarray,
    xlabel: str = '',
    ylabel: str = '',
    title: str = '',
    cbar_label: str = '',  # noqa: ARG001 - Reserved for future colorbar implementation
    center_zero: bool = False,
    cmap: Optional[str] = None,
    annotate: bool = True,
    fmt: str = '.1f',
    **kwargs
) -> Tuple[plt.Axes, mpl.image.AxesImage]:
    """
    Format a heatmap with standardized styling.
    
    Args:
        ax: Matplotlib axis
        data: 2D array of heatmap values
        xlabel: X-axis label
        ylabel: Y-axis label
        title: Plot title
        cbar_label: Colorbar label
        center_zero: Center colormap on zero (for diverging data)
        cmap: Colormap name (default: diverging if center_zero else sequential)
        annotate: Add value annotations to cells
        fmt: Format string for annotations
        **kwargs: Additional arguments passed to format_plot
        
    Returns:
        Formatted axis and image object
    """
    if cmap is None:
        cmap = 'RdYlGn_r' if center_zero else 'viridis'
    
    # Determine color scale
    if center_zero:
        vmax = max(abs(np.nanmin(data)), abs(np.nanmax(data)))
        vmin = -vmax
    else:
        vmin, vmax = np.nanmin(data), np.nanmax(data)
    
    # Create heatmap
    im = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax, aspect='auto')
    
    # Add annotations if requested
    if annotate:
        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                val = data[i, j]
                if not np.isnan(val):
                    # Choose text color based on background
                    if center_zero:
                        text_color = 'white' if abs(val) > vmax*0.5 else 'black'
                    else:
                        text_color = 'white' if val > (vmin + 0.7*(vmax-vmin)) else 'black'
                    
                    ax.text(j, i, f'{val:{fmt}}', 
                           ha='center', va='center', color=text_color, fontsize=9)
    
    # Apply standard formatting
    format_plot(
        ax,
        xlabel=xlabel,
        ylabel=ylabel,
        title=title,
        grid=False,
        **kwargs
    )
    
    return ax, im


def format_comparison_plot(
    ax: plt.Axes,
    xlabel: str = '',
    ylabel: str = '% Change',
    title: str = '',
    show_zero_line: bool = True,
    **kwargs
) -> plt.Axes:
    """
    Format a comparison/percent change plot.
    
    Args:
        ax: Matplotlib axis
        xlabel: X-axis label
        ylabel: Y-axis label (default: '% Change')
        title: Plot title
        show_zero_line: Draw horizontal line at y=0
        **kwargs: Additional arguments passed to format_plot
        
    Returns:
        Formatted axis
    """
    if show_zero_line:
        ax.axhline(y=0, color='black', linewidth=1.0, linestyle='-', alpha=0.5, zorder=1)
    
    format_plot(
        ax,
        xlabel=xlabel,
        ylabel=ylabel,
        title=title,
        **kwargs
    )
    
    return ax


def create_scenario_colormap(n_scenarios: int = 25) -> List[str]:
    """
    Create a color list for scenario plots (0% to 100% vegetation).
    
    Args:
        n_scenarios: Number of scenarios
        
    Returns:
        List of color hex codes
    """
    from matplotlib.colors import LinearSegmentedColormap
    
    # Create gradient from red (low vegetation) to green (high vegetation)
    colors = ['#E74C3C', '#F39C12', '#F1C40F', '#2ECC71', '#27AE60']
    n_bins = 100
    cmap = LinearSegmentedColormap.from_list('scenario', colors, N=n_bins)
    
    # Sample colors for scenarios
    indices = np.linspace(0, n_bins-1, n_scenarios).astype(int)
    return [mpl.colors.rgb2hex(cmap(i/n_bins)) for i in indices]


# =============================================================================
# FIGURE CREATION HELPERS
# =============================================================================

def create_figure(
    nrows: int = 1,
    ncols: int = 1,
    figsize: Optional[Tuple[float, float]] = None,
    style: str = 'default',
    sharex: bool = False,
    sharey: bool = False,
    **kwargs
) -> Tuple[plt.Figure, Union[plt.Axes, np.ndarray]]:
    """
    Create a figure with project styling applied.
    
    Args:
        nrows: Number of subplot rows
        ncols: Number of subplot columns
        figsize: Figure size (width, height) in inches
        style: Style preset to apply
        sharex: Share x-axis across subplots
        sharey: Share y-axis across subplots
        **kwargs: Additional arguments passed to plt.subplots()
        
    Returns:
        Figure and axis (or array of axes)
    """
    # Set style
    set_project_style(style)
    
    # Determine figure size if not provided
    if figsize is None:
        width = 6 * ncols
        height = 4 * nrows
        figsize = (width, height)
    
    # Create figure
    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=ncols,
        figsize=figsize,
        sharex=sharex,
        sharey=sharey,
        **kwargs
    )
    
    return fig, axes


# =============================================================================
# EXAMPLE USAGE (can be removed or kept for documentation)
# =============================================================================

if __name__ == '__main__':
    """
    Example usage of plot formatting functions.
    Run this script directly to see formatting examples.
    """
    # Set project style
    set_project_style('default')
    
    # Example 1: Basic line plot
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.linspace(0, 10, 100)
    y1 = np.sin(x)
    y2 = np.cos(x)
    
    ax.plot(x, y1, label='Sin', color=get_project_colors('primary_blue'), linewidth=2)
    ax.plot(x, y2, label='Cos', color=get_project_colors('primary_green'), linewidth=2)
    
    format_plot(
        ax,
        xlabel='X axis',
        ylabel='Y axis',
        title='Example Line Plot',
        legend=True,
        xlim=(0, 10),
        ylim=(-1.5, 1.5)
    )
    
    plt.savefig('example_line_plot.png', dpi=300, bbox_inches='tight')
    print("Saved example_line_plot.png")
    
    # Example 2: Heatmap
    fig, ax = plt.subplots(figsize=(8, 6))
    data = np.random.randn(5, 5) * 10
    
    format_heatmap(
        ax,
        data,
        xlabel='Landscape Ratio',
        ylabel='Facade Ratio',
        title='Example Heatmap',
        cbar_label='% Change',
        center_zero=True,
        annotate=True
    )
    
    plt.savefig('example_heatmap.png', dpi=300, bbox_inches='tight')
    print("Saved example_heatmap.png")
    
    plt.close('all')
    print("\nFormatting examples complete!")
