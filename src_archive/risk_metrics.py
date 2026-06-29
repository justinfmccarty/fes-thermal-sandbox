"""
Risk Metrics Calculator - Leaf Temperature Focus

Calculates heat stress metrics based on leaf temperature.
All default parameters are loaded from config.yaml via config_locator.

Simplified to focus on T_leaf only because:
- VPD effects are already captured in the Li2023 CEB leaf temperature calculation
- Soil moisture is speculative without real data
- Leaf temperature is the primary driver of photosynthetic heat damage
"""

import pandas as pd
import numpy as np
from typing import Optional

from config_locator import get_config


def get_T_crit() -> float:
    """Get critical leaf temperature from config."""
    config = get_config()
    return config.model.risk.T_crit


def calculate_heat_stress_hours(
    T_leaf: np.ndarray,
    T_crit: Optional[float] = None
) -> int:
    """
    Calculate number of hours where leaf temperature exceeds critical threshold.
    
    Args:
        T_leaf: Array of leaf temperatures [C]
        T_crit: Critical temperature threshold [C] (uses config default if None)
        
    Returns:
        Number of exceedance hours
    """
    if T_crit is None:
        T_crit = get_T_crit()
    return int(np.sum(T_leaf > T_crit))


def calculate_degree_hours(
    T_leaf: np.ndarray,
    T_crit: Optional[float] = None
) -> float:
    """
    Calculate degree-hours above critical temperature.
    
    This is a more meaningful metric than simple exceedance hours because
    it captures both duration AND severity of heat stress.
    
    Degree-hours = sum(max(0, T_leaf - T_crit))
    
    Args:
        T_leaf: Array of leaf temperatures [C]
        T_crit: Critical temperature [C] (uses config default if None)
        
    Returns:
        Degree-hours [C-hours]
    """
    if T_crit is None:
        T_crit = get_T_crit()
    excess = np.maximum(0.0, T_leaf - T_crit)
    return float(np.sum(excess))


def calculate_stress_summary(
    results_df: pd.DataFrame,
    T_crit: Optional[float] = None
) -> pd.DataFrame:
    """
    Calculate heat stress summary for all trees.
    
    Focuses on leaf temperature metrics only.
    
    Args:
        results_df: DataFrame with columns: tree_id, hour, T_leaf
        T_crit: Critical temperature [C] (uses config default if None)
        
    Returns:
        DataFrame with stress metrics per tree:
        - tree_id
        - heat_stress_hours: Hours where T_leaf > T_crit
        - degree_hours: Cumulative degrees above T_crit
        - mean_Tleaf_C: Mean leaf temperature
        - max_Tleaf_C: Maximum leaf temperature
    """
    if T_crit is None:
        T_crit = get_T_crit()
    
    summary_rows = []
    
    for tree_id in results_df['tree_id'].unique():
        tree_data = results_df[results_df['tree_id'] == tree_id]
        T_leaf = tree_data['T_leaf'].values
        
        heat_stress_hours = calculate_heat_stress_hours(T_leaf, T_crit)
        degree_hours = calculate_degree_hours(T_leaf, T_crit)
        
        summary_rows.append({
            'tree_id': tree_id,
            'heat_stress_hours': heat_stress_hours,
            'degree_hours': degree_hours,
            'mean_Tleaf_C': float(np.mean(T_leaf)),
            'max_Tleaf_C': float(np.max(T_leaf))
        })
    
    return pd.DataFrame(summary_rows)
