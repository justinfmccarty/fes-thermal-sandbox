"""Heat-stress metrics from leaf temperature.

PORT FROM: src_archive/risk_metrics.py
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from treeheat.config import get_config

__all__ = [
    "calculate_degree_hours",
    "calculate_extended_stress_summary",
    "calculate_heat_stress_hours",
    "calculate_stress_summary",
    "get_T_crit",
]


def get_T_crit(cfg: dict[str, Any] | None = None) -> float:
    """Get critical leaf temperature from config."""
    if cfg is None:
        cfg = get_config()
    return float(cfg["model"]["risk"]["T_crit"])


def calculate_heat_stress_hours(T_leaf: np.ndarray, T_crit: float | None = None) -> int:
    """Count hours where leaf temperature exceeds critical threshold."""
    if T_crit is None:
        T_crit = get_T_crit()
    return int(np.sum(T_leaf > T_crit))


def calculate_degree_hours(T_leaf: np.ndarray, T_crit: float | None = None) -> float:
    """Cumulative degree-hours above T_crit."""
    if T_crit is None:
        T_crit = get_T_crit()
    excess = np.maximum(0.0, T_leaf - T_crit)
    return float(np.sum(excess))


def calculate_stress_summary(
    results_df: pd.DataFrame,
    T_crit: float | None = None,
    cfg: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Per-tree heat stress summary from hourly biophysical results."""
    if T_crit is None:
        T_crit = get_T_crit(cfg)

    summary_rows: list[dict[str, Any]] = []
    for tree_id in results_df["tree_id"].unique():
        tree_data = results_df[results_df["tree_id"] == tree_id]
        T_leaf = tree_data["T_leaf"].values

        summary_rows.append(
            {
                "tree_id": tree_id,
                "heat_stress_hours": calculate_heat_stress_hours(T_leaf, T_crit),
                "degree_hours": calculate_degree_hours(T_leaf, T_crit),
                "mean_Tleaf_C": float(np.mean(T_leaf)),
                "max_Tleaf_C": float(np.max(T_leaf)),
            }
        )

    return pd.DataFrame(summary_rows)


def calculate_extended_stress_summary(
    results_df: pd.DataFrame,
    T_crit: float | None = None,
    cfg: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Stress summary with MRT and Tsurf metrics per tree."""
    summary = calculate_stress_summary(results_df, T_crit, cfg)

    mrt_metrics: list[dict[str, Any]] = []
    tsurf_metrics: list[dict[str, Any]] = []
    for tree_id in results_df["tree_id"].unique():
        tree_data = results_df[results_df["tree_id"] == tree_id]
        mrt_metrics.append(
            {
                "tree_id": tree_id,
                "mean_MRT_C": float(tree_data["MRT"].mean()),
                "max_MRT_C": float(tree_data["MRT"].max()),
            }
        )
        tsurf_metrics.append(
            {
                "tree_id": tree_id,
                "mean_Tsurf_C": float(tree_data["Tsurf"].mean()),
                "max_Tsurf_C": float(tree_data["Tsurf"].max()),
            }
        )

    summary = summary.merge(pd.DataFrame(mrt_metrics), on="tree_id")
    summary = summary.merge(pd.DataFrame(tsurf_metrics), on="tree_id")
    return summary
