"""
Visualization Module

Creates plots and charts for tree stress analysis results.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from typing import Dict, List, Optional, Tuple
import os


def plot_stress_over_time(
    results_df: pd.DataFrame,
    tree_ids: Optional[List[str]] = None,
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 6)
):
    """
    Plot stress metrics over time for selected trees.
    
    Args:
        results_df: DataFrame with columns ['hour', 'tree_id', 'T_leaf', 'ET', 'gc', 'theta']
        tree_ids: List of tree IDs to plot, or None for all trees
        output_path: Path to save figure, or None to display
        figsize: Figure size (width, height)
    """
    if tree_ids is None:
        tree_ids = results_df['tree_id'].unique()[:10]  # Limit to 10 trees for readability
    
    fig, axes = plt.subplots(2, 2, figsize=figsize)
    fig.suptitle('Tree Stress Metrics Over Time', fontsize=14, fontweight='bold')
    
    for tree_id in tree_ids[:5]:  # Limit to 5 trees per plot
        tree_data = results_df[results_df['tree_id'] == tree_id]
        
        if len(tree_data) == 0:
            continue
        
        # Plot leaf temperature
        axes[0, 0].plot(tree_data['hour'], tree_data['T_leaf'], label=f'Tree {tree_id}', alpha=0.7)
        axes[0, 0].axhline(y=42.0, color='r', linestyle='--', alpha=0.5, label='Critical temp' if tree_id == tree_ids[0] else '')
        axes[0, 0].set_xlabel('Hour of Year')
        axes[0, 0].set_ylabel('Leaf Temperature (°C)')
        axes[0, 0].set_title('Leaf Temperature')
        axes[0, 0].grid(True, alpha=0.3)
        
        # Plot transpiration
        axes[0, 1].plot(tree_data['hour'], tree_data['ET'], label=f'Tree {tree_id}', alpha=0.7)
        axes[0, 1].set_xlabel('Hour of Year')
        axes[0, 1].set_ylabel('Transpiration (mm/h)')
        axes[0, 1].set_title('Transpiration Rate')
        axes[0, 1].grid(True, alpha=0.3)
        
        # Plot stomatal conductance
        axes[1, 0].plot(tree_data['hour'], tree_data['gc'], label=f'Tree {tree_id}', alpha=0.7)
        axes[1, 0].set_xlabel('Hour of Year')
        axes[1, 0].set_ylabel('Stomatal Conductance (mol/m²/s)')
        axes[1, 0].set_title('Stomatal Conductance')
        axes[1, 0].grid(True, alpha=0.3)
        
        # Plot soil moisture
        axes[1, 1].plot(tree_data['hour'], tree_data['theta'], label=f'Tree {tree_id}', alpha=0.7)
        axes[1, 1].axhline(y=0.3, color='orange', linestyle='--', alpha=0.5, label='Critical' if tree_id == tree_ids[0] else '')
        axes[1, 1].axhline(y=0.1, color='r', linestyle='--', alpha=0.5, label='Wilting' if tree_id == tree_ids[0] else '')
        axes[1, 1].set_xlabel('Hour of Year')
        axes[1, 1].set_ylabel('Soil Moisture (m³/m³)')
        axes[1, 1].set_title('Soil Moisture')
        axes[1, 1].grid(True, alpha=0.3)
    
    # Add legend to first subplot only
    axes[0, 0].legend(loc='best', fontsize=8)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved plot to: {output_path}")
    else:
        plt.show()
    
    plt.close()


def plot_stress_heatmap(
    tree_points: pd.DataFrame,
    stress_metrics: pd.DataFrame,
    metric: str = 'risk_reduction',
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 8)
):
    """
    Create heat map of tree stress by location.
    
    Args:
        tree_points: DataFrame with columns ['tree_id', 'xcoord', 'ycoord']
        stress_metrics: DataFrame with columns ['tree_id', metric]
        metric: Metric to visualize
        output_path: Path to save figure, or None to display
        figsize: Figure size (width, height)
    """
    # Merge tree points with stress metrics
    merged = pd.merge(tree_points[['tree_id', 'xcoord', 'ycoord']], 
                     stress_metrics[['tree_id', metric]],
                     on='tree_id', how='inner')
    
    if len(merged) == 0:
        print(f"Warning: No matching trees found for heatmap")
        return
    
    fig, ax = plt.subplots(figsize=figsize)
    
    scatter = ax.scatter(merged['xcoord'], merged['ycoord'], 
                        c=merged[metric], cmap='RdYlGn_r', 
                        s=50, alpha=0.6, edgecolors='black', linewidth=0.5)
    
    ax.set_xlabel('X Coordinate')
    ax.set_ylabel('Y Coordinate')
    ax.set_title(f'Tree Stress Heatmap: {metric}')
    ax.grid(True, alpha=0.3)
    
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label(metric, rotation=270, labelpad=20)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved heatmap to: {output_path}")
    else:
        plt.show()
    
    plt.close()


def plot_scenario_comparison(
    aggregated_results: pd.DataFrame,
    metric: str = 'mean_risk_reduction',
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 6)
):
    """
    Create bar chart comparing scenarios.
    
    Args:
        aggregated_results: DataFrame from aggregate_stress_metrics()
        metric: Metric to compare
        output_path: Path to save figure, or None to display
        figsize: Figure size (width, height)
    """
    if metric not in aggregated_results.columns:
        print(f"Warning: Metric '{metric}' not found in aggregated results")
        return
    
    # Sort by metric
    sorted_results = aggregated_results.sort_values(by=metric, ascending=False)
    
    fig, ax = plt.subplots(figsize=figsize)
    
    colors = ['green' if x > 0 else 'red' for x in sorted_results[metric]]
    bars = ax.bar(range(len(sorted_results)), sorted_results[metric], color=colors, alpha=0.7)
    
    ax.set_xlabel('Scenario')
    ax.set_ylabel(metric.replace('_', ' ').title())
    ax.set_title(f'Scenario Comparison: {metric.replace("_", " ").title()}')
    ax.set_xticks(range(len(sorted_results)))
    ax.set_xticklabels(sorted_results['scenario_id'], rotation=45, ha='right')
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, (bar, val) in enumerate(zip(bars, sorted_results[metric])):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{val:.2f}',
               ha='center', va='bottom' if height > 0 else 'top', fontsize=8)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved comparison plot to: {output_path}")
    else:
        plt.show()
    
    plt.close()


def plot_material_impact(
    material_impacts: pd.DataFrame,
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 8)
):
    """
    Create scatter plot showing material impact.
    
    Args:
        material_impacts: DataFrame from identify_most_impactful_materials()
        output_path: Path to save figure, or None to display
        figsize: Figure size (width, height)
    """
    if len(material_impacts) == 0:
        print("Warning: No material impact data to plot")
        return
    
    fig, ax = plt.subplots(figsize=figsize)
    
    scatter = ax.scatter(
        material_impacts['landscape_naturalness'],
        material_impacts['facade_naturalness'],
        c=material_impacts['mean_risk_reduction'],
        s=100,
        cmap='RdYlGn_r',
        alpha=0.7,
        edgecolors='black',
        linewidth=1
    )
    
    ax.set_xlabel('Landscape Naturalness')
    ax.set_ylabel('Facade Naturalness')
    ax.set_title('Material Impact on Tree Stress Reduction')
    ax.grid(True, alpha=0.3)
    
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Mean Risk Reduction', rotation=270, labelpad=20)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved material impact plot to: {output_path}")
    else:
        plt.show()
    
    plt.close()


def plot_box_plot_comparison(
    risk_results: Dict[str, pd.DataFrame],
    metric: str = 'risk_reduction',
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 6)
):
    """
    Create box plot comparing distributions across scenarios.
    
    Args:
        risk_results: Dictionary mapping scenario_id -> DataFrame with tree risk metrics
        metric: Metric to compare
        output_path: Path to save figure, or None to display
        figsize: Figure size (width, height)
    """
    data_to_plot = []
    labels = []
    
    for scenario_id, df in risk_results.items():
        if df is None or len(df) == 0 or metric not in df.columns:
            continue
        
        data_to_plot.append(df[metric].dropna().values)
        labels.append(scenario_id)
    
    if len(data_to_plot) == 0:
        print(f"Warning: No data found for metric '{metric}'")
        return
    
    fig, ax = plt.subplots(figsize=figsize)
    
    bp = ax.boxplot(data_to_plot, labels=labels, patch_artist=True)
    
    # Color boxes
    colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(bp['boxes'])))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    
    ax.set_xlabel('Scenario')
    ax.set_ylabel(metric.replace('_', ' ').title())
    ax.set_title(f'Distribution Comparison: {metric.replace("_", " ").title()}')
    ax.axhline(y=0, color='black', linestyle='--', linewidth=0.8, alpha=0.5)
    ax.grid(True, alpha=0.3, axis='y')
    plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved box plot to: {output_path}")
    else:
        plt.show()
    
    plt.close()


def generate_all_visualizations(
    aggregated_results: pd.DataFrame,
    risk_results: Dict[str, pd.DataFrame],
    material_impacts: pd.DataFrame,
    tree_points: pd.DataFrame,
    output_dir: str = 'visualizations'
):
    """
    Generate all visualizations and save to output directory.
    
    Args:
        aggregated_results: DataFrame from aggregate_stress_metrics()
        risk_results: Dictionary mapping scenario_id -> DataFrame with tree risk metrics
        material_impacts: DataFrame from identify_most_impactful_materials()
        tree_points: DataFrame with tree locations
        output_dir: Directory to save visualizations
    """
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Generating visualizations in {output_dir}...")
    
    # Scenario comparison
    plot_scenario_comparison(
        aggregated_results,
        metric='mean_risk_reduction',
        output_path=os.path.join(output_dir, 'scenario_comparison.png')
    )
    
    # Material impact
    if len(material_impacts) > 0:
        plot_material_impact(
            material_impacts,
            output_path=os.path.join(output_dir, 'material_impact.png')
        )
    
    # Box plot comparison
    plot_box_plot_comparison(
        risk_results,
        metric='risk_reduction',
        output_path=os.path.join(output_dir, 'box_plot_comparison.png')
    )
    
    # Heat map (using first scenario with data)
    for scenario_id, df in risk_results.items():
        if df is not None and len(df) > 0 and 'risk_reduction' in df.columns:
            plot_stress_heatmap(
                tree_points,
                df,
                metric='risk_reduction',
                output_path=os.path.join(output_dir, f'heatmap_{scenario_id}.png')
            )
            break
    
    print(f"Visualizations saved to {output_dir}")

