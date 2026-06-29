"""
Results Analysis Module

Aggregates and analyzes tree stress results across scenarios.
Provides statistical comparisons and material impact rankings.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from scipy import stats


def aggregate_stress_metrics(risk_results: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Aggregate stress metrics across all trees for each scenario.
    
    Args:
        risk_results: Dictionary mapping scenario_id -> DataFrame with tree risk metrics
        
    Returns:
        DataFrame with aggregated metrics per scenario
    """
    aggregated = []
    
    for scenario_id, df in risk_results.items():
        if df is None or len(df) == 0:
            continue
        
        agg_row = {
            'scenario_id': scenario_id,
            'mean_risk_index': df['scenario_risk_index'].mean() if 'scenario_risk_index' in df.columns else np.nan,
            'median_risk_index': df['scenario_risk_index'].median() if 'scenario_risk_index' in df.columns else np.nan,
            'std_risk_index': df['scenario_risk_index'].std() if 'scenario_risk_index' in df.columns else np.nan,
            'mean_risk_reduction': df['risk_reduction'].mean() if 'risk_reduction' in df.columns else np.nan,
            'median_risk_reduction': df['risk_reduction'].median() if 'risk_reduction' in df.columns else np.nan,
            'total_risk_reduction': df['risk_reduction'].sum() if 'risk_reduction' in df.columns else np.nan,
            'mean_heat_hours': df['scenario_heat_hours'].mean() if 'scenario_heat_hours' in df.columns else np.nan,
            'mean_heat_hours_reduction': df['heat_hours_reduction'].mean() if 'heat_hours_reduction' in df.columns else np.nan,
            'n_trees': len(df),
            'n_trees_benefited': (df['risk_reduction'] > 0).sum() if 'risk_reduction' in df.columns else 0,
            'n_trees_harmed': (df['risk_reduction'] < 0).sum() if 'risk_reduction' in df.columns else 0
        }
        
        aggregated.append(agg_row)
    
    return pd.DataFrame(aggregated)


def compare_scenarios(
    baseline_results: pd.DataFrame,
    scenario_results: Dict[str, pd.DataFrame],
    metric: str = 'risk_reduction'
) -> pd.DataFrame:
    """
    Compare scenarios against baseline.
    
    Args:
        baseline_results: Baseline risk results DataFrame
        scenario_results: Dictionary mapping scenario_id -> scenario risk results DataFrame
        metric: Metric to compare ('risk_reduction', 'scenario_risk_index', etc.)
        
    Returns:
        DataFrame with comparison statistics
    """
    comparisons = []
    
    baseline_mean = baseline_results[metric].mean() if metric in baseline_results.columns else 0.0
    
    for scenario_id, df in scenario_results.items():
        if df is None or len(df) == 0 or metric not in df.columns:
            continue
        
        scenario_mean = df[metric].mean()
        difference = scenario_mean - baseline_mean
        
        # Statistical test (paired t-test if same trees)
        if 'tree_id' in df.columns and 'tree_id' in baseline_results.columns:
            # Match trees
            merged = pd.merge(
                baseline_results[['tree_id', metric]],
                df[['tree_id', metric]],
                on='tree_id',
                suffixes=('_baseline', '_scenario')
            )
            
            if len(merged) > 1:
                t_stat, p_value = stats.ttest_rel(
                    merged[f'{metric}_baseline'],
                    merged[f'{metric}_scenario']
                )
            else:
                t_stat, p_value = np.nan, np.nan
        else:
            t_stat, p_value = np.nan, np.nan
        
        comparisons.append({
            'scenario_id': scenario_id,
            'baseline_mean': baseline_mean,
            'scenario_mean': scenario_mean,
            'difference': difference,
            'percent_change': (difference / baseline_mean * 100) if baseline_mean != 0 else np.nan,
            't_statistic': t_stat,
            'p_value': p_value,
            'significant': p_value < 0.05 if pd.notna(p_value) else False
        })
    
    return pd.DataFrame(comparisons)


def rank_scenarios_by_impact(
    aggregated_results: pd.DataFrame,
    metric: str = 'mean_risk_reduction',
    ascending: bool = False
) -> pd.DataFrame:
    """
    Rank scenarios by impact (risk reduction).
    
    Args:
        aggregated_results: DataFrame from aggregate_stress_metrics()
        metric: Metric to rank by
        ascending: If True, rank ascending (lower is better), else descending (higher is better)
        
    Returns:
        DataFrame sorted by impact
    """
    if metric not in aggregated_results.columns:
        raise ValueError(f"Metric '{metric}' not found in aggregated results")
    
    ranked = aggregated_results.sort_values(by=metric, ascending=ascending).copy()
    ranked['rank'] = range(1, len(ranked) + 1)
    
    return ranked


def identify_most_impactful_materials(
    scenario_materials: Dict[str, Dict],
    aggregated_results: pd.DataFrame
) -> pd.DataFrame:
    """
    Identify which material combinations are most impactful.
    
    Args:
        scenario_materials: Dictionary mapping scenario_id -> {
            'landscape_material': str,
            'facade_material': str,
            'instruction': Tuple[float, float]
        }
        aggregated_results: DataFrame from aggregate_stress_metrics()
        
    Returns:
        DataFrame with material impact analysis
    """
    material_impacts = []
    
    for scenario_id, materials in scenario_materials.items():
        scenario_result = aggregated_results[aggregated_results['scenario_id'] == scenario_id]
        
        if len(scenario_result) == 0:
            continue
        
        impact = {
            'scenario_id': scenario_id,
            'landscape_material': materials.get('landscape_material', 'unknown'),
            'facade_material': materials.get('facade_material', 'unknown'),
            'landscape_naturalness': materials.get('instruction', (0, 0))[0] if materials.get('instruction') else np.nan,
            'facade_naturalness': materials.get('instruction', (0, 0))[1] if materials.get('instruction') else np.nan,
            'mean_risk_reduction': scenario_result['mean_risk_reduction'].iloc[0] if 'mean_risk_reduction' in scenario_result.columns else np.nan,
            'rank': scenario_result['rank'].iloc[0] if 'rank' in scenario_result.columns else np.nan
        }
        
        material_impacts.append(impact)
    
    return pd.DataFrame(material_impacts)


def calculate_tree_specific_impact(
    risk_results: Dict[str, pd.DataFrame],
    tree_id: Optional[str] = None
) -> pd.DataFrame:
    """
    Calculate impact for specific trees or all trees.
    
    Args:
        risk_results: Dictionary mapping scenario_id -> DataFrame with tree risk metrics
        tree_id: Specific tree ID to analyze, or None for all trees
        
    Returns:
        DataFrame with tree-specific impacts
    """
    tree_impacts = []
    
    for scenario_id, df in risk_results.items():
        if df is None or len(df) == 0:
            continue
        
        if tree_id is not None:
            df = df[df['tree_id'] == tree_id]
            if len(df) == 0:
                continue
        
        for _, row in df.iterrows():
            tree_impacts.append({
                'scenario_id': scenario_id,
                'tree_id': row.get('tree_id', 'unknown'),
                'risk_reduction': row.get('risk_reduction', np.nan),
                'baseline_risk_index': row.get('baseline_risk_index', np.nan),
                'scenario_risk_index': row.get('scenario_risk_index', np.nan),
                'heat_hours_reduction': row.get('heat_hours_reduction', np.nan)
            })
    
    return pd.DataFrame(tree_impacts)


def generate_summary_statistics(
    aggregated_results: pd.DataFrame,
    risk_results: Dict[str, pd.DataFrame]
) -> Dict:
    """
    Generate summary statistics for all scenarios.
    
    Args:
        aggregated_results: DataFrame from aggregate_stress_metrics()
        risk_results: Dictionary mapping scenario_id -> DataFrame with tree risk metrics
        
    Returns:
        Dictionary with summary statistics
    """
    summary = {
        'n_scenarios': len(aggregated_results),
        'n_trees': len(risk_results.get('baseline', pd.DataFrame())) if 'baseline' in risk_results else 0,
        'best_scenario': aggregated_results.loc[aggregated_results['mean_risk_reduction'].idxmax(), 'scenario_id'] if 'mean_risk_reduction' in aggregated_results.columns and len(aggregated_results) > 0 else None,
        'worst_scenario': aggregated_results.loc[aggregated_results['mean_risk_reduction'].idxmin(), 'scenario_id'] if 'mean_risk_reduction' in aggregated_results.columns and len(aggregated_results) > 0 else None,
        'mean_risk_reduction_all': aggregated_results['mean_risk_reduction'].mean() if 'mean_risk_reduction' in aggregated_results.columns else np.nan,
        'max_risk_reduction': aggregated_results['mean_risk_reduction'].max() if 'mean_risk_reduction' in aggregated_results.columns else np.nan,
        'min_risk_reduction': aggregated_results['mean_risk_reduction'].min() if 'mean_risk_reduction' in aggregated_results.columns else np.nan,
        'scenarios_with_benefit': (aggregated_results['mean_risk_reduction'] > 0).sum() if 'mean_risk_reduction' in aggregated_results.columns else 0,
        'scenarios_with_harm': (aggregated_results['mean_risk_reduction'] < 0).sum() if 'mean_risk_reduction' in aggregated_results.columns else 0
    }
    
    return summary

