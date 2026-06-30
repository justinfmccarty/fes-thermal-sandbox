"""Publication-quality plots for cross-scenario analysis.

PORT FROM: src_archive/plots.py + src_archive/plot_formatting.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

__all__ = [
    "generate_all_plots",
    "plot_combined_sensitivity",
    "plot_risk_heatmap",
    "plot_scenario_concept",
    "plot_sensitivity_by_surface_type",
]


def _apply_style() -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["font.size"] = 11


def plot_risk_heatmap(
    pct_df: pd.DataFrame,
    output_path: Path | str | None = None,
    figsize: tuple[float, float] = (8, 7),
    cmap: str = "RdYlGn_r",
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=figsize)
    pivot_data = pct_df.pivot(
        index="facade_ratio",
        columns="landscape_ratio",
        values="degree_hours_pct_change",
    )
    vmax = max(abs(pivot_data.min().min()), abs(pivot_data.max().max()))
    vmin = -vmax
    im = ax.imshow(pivot_data.values, cmap=cmap, vmin=vmin, vmax=vmax, aspect="equal")
    plt.colorbar(im, ax=ax, label="% Change in Weighted Risk Index")
    for i in range(len(pivot_data.index)):
        for j in range(len(pivot_data.columns)):
            val = pivot_data.values[i, j]
            color = "white" if abs(val) > vmax * 0.5 else "black"
            ax.text(j, i, f"{val:.1f}%", ha="center", va="center", color=color, fontsize=10)
    ax.set_xticks(range(len(pivot_data.columns)))
    ax.set_xticklabels([f"{x:.0%}" for x in pivot_data.columns])
    ax.set_yticks(range(len(pivot_data.index)))
    ax.set_yticklabels([f"{y:.0%}" for y in pivot_data.index])
    ax.set_xlabel("Landscape Vegetation Ratio")
    ax.set_ylabel("Facade Vegetation Ratio")
    ax.set_title("Percent Change in Tree Risk Index\n(Relative to Middle Scenario 50%/50%)")
    plt.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
    return fig


def plot_combined_sensitivity(
    sensitivity_df: pd.DataFrame,
    output_path: Path | str | None = None,
    figsize: tuple[float, float] = (12, 5),
    cmap: str = "BrBG",
) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    regression = sensitivity_df.attrs.get("regression", {})
    valid = sensitivity_df.dropna(subset=["mean_albedo", "degree_hours_pct_change"])

    for ax, x_col, reg_key, xlabel, title in [
        (axes[0], "mean_albedo", "risk_albedo", "Area-Weighted Mean Albedo", "Risk Sensitivity to Surface Albedo"),
        (axes[1], "mean_emissivity", "risk_emissivity", "Area-Weighted Mean Emissivity", "Risk Sensitivity to Surface Emissivity"),
    ]:
        scatter = ax.scatter(
            valid[x_col],
            valid["degree_hours_pct_change"],
            c=valid["landscape_ratio"],
            cmap=cmap,
            s=80,
            edgecolor="black",
            alpha=0.7,
        )
        fig.colorbar(scatter, ax=ax, label="Landscape Vegetation Ratio")
        reg = regression.get(reg_key)
        if reg:
            x_line = np.linspace(valid[x_col].min(), valid[x_col].max(), 100)
            y_line = reg["slope"] * x_line + reg["intercept"]
            ax.plot(
                x_line,
                y_line,
                "r--",
                linewidth=2,
                label=f"y = {reg['slope']:.1f}x + {reg['intercept']:.1f}\nR² = {reg['r2']:.3f}",
            )
            ax.legend(loc="best")
        ax.axhline(y=0, color="gray", linestyle="-", alpha=0.5)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("% Change in Risk Index")
        ax.set_title(title)

    plt.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
    return fig


def plot_sensitivity_by_surface_type(
    sensitivity_df: pd.DataFrame,
    output_path: Path | str | None = None,
    figsize: tuple[float, float] = (16, 4),
    cmap: str = "BrBG",
) -> plt.Figure:
    fig, axes = plt.subplots(1, 4, figsize=figsize, sharey=True)
    regression = sensitivity_df.attrs.get("regression", {})
    configs = [
        ("landscape_albedo", "landscape_ratio", "risk_landscape_albedo", "Landscape Albedo", "Risk vs Landscape Albedo"),
        ("landscape_emissivity", "landscape_ratio", "risk_landscape_emissivity", "Landscape Emissivity", "Risk vs Landscape Emissivity"),
        ("facade_albedo", "facade_ratio", "risk_facade_albedo", "Facade Albedo", "Risk vs Facade Albedo"),
        ("facade_emissivity", "facade_ratio", "risk_facade_emissivity", "Facade Emissivity", "Risk vs Facade Emissivity"),
    ]
    for ax, (x_col, color_col, reg_key, xlabel, title) in zip(axes, configs):
        valid = sensitivity_df.dropna(subset=[x_col, "degree_hours_pct_change"])
        if len(valid) == 0:
            continue
        scatter = ax.scatter(
            valid[x_col],
            valid["degree_hours_pct_change"],
            c=valid[color_col],
            cmap=cmap,
            s=80,
            edgecolor="black",
            alpha=0.7,
            vmin=0,
            vmax=1,
        )
        reg = regression.get(reg_key)
        if reg:
            x_line = np.linspace(valid[x_col].min(), valid[x_col].max(), 100)
            y_line = reg["slope"] * x_line + reg["intercept"]
            ax.plot(x_line, y_line, "r--", linewidth=2)
        ax.axhline(y=0, color="gray", linestyle="-", alpha=0.5)
        ax.set_xlabel(xlabel)
        ax.set_title(title)
        fig.colorbar(scatter, ax=ax, shrink=0.8, pad=0.02)
    axes[0].set_ylabel("% Change in Risk Index")
    plt.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
    return fig


def plot_scenario_concept(
    sensitivity_df: pd.DataFrame,
    output_path: Path | str | None = None,
    figsize: tuple[float, float] = (8, 6),
) -> plt.Figure:
    predefined = [(x, y) for x in np.arange(0, 1.1, 0.25) for y in np.arange(0, 1.1, 0.25)]
    plot_df = pd.DataFrame(predefined, columns=["landscape_ratio", "facade_ratio"])
    fig, ax = plt.subplots(figsize=figsize)
    ax.vlines(0.5, -0.1, 1.1, color="black", zorder=10)
    ax.hlines(0.5, -0.1, 1.1, color="black", zorder=10)

    albedo_values = sensitivity_df["mean_albedo"].values
    emissivity_values = sensitivity_df["mean_emissivity"].values
    size_min, size_max = 10, 500
    em_min, em_max = emissivity_values.min(), emissivity_values.max()
    sizes = size_min + (emissivity_values - em_min) / (em_max - em_min) * (size_max - size_min)

    scatter = ax.scatter(
        plot_df["landscape_ratio"],
        plot_df["facade_ratio"],
        c=albedo_values,
        s=sizes,
        vmin=0,
        vmax=0.6,
        cmap="binary_r",
        ec="none",
        marker="o",
        zorder=100,
    )
    axins = inset_axes(
        ax,
        width="5%",
        height="60%",
        loc="right",
        bbox_to_anchor=(0.47, 0, 0.8, 0.8),
        bbox_transform=ax.transAxes,
        borderpad=0,
    )
    fig.colorbar(scatter, cax=axins, orientation="vertical", label="Mean Albedo")
    ax.set_xlabel("Landscape Vegetation Ratio")
    ax.set_ylabel("Facade Vegetation Ratio")
    ax.set_title("Scenario Material Properties\n(Color=Albedo, Size=Emissivity)")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    plt.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
    return fig


def generate_all_plots(
    pct_df: pd.DataFrame,
    sensitivity_df: pd.DataFrame,
    master_summary: pd.DataFrame,
    results: dict[str, pd.DataFrame] | None,
    plots_dir: Path,
    cfg: dict[str, Any] | None = None,
) -> None:
    """Generate all publication figures used in the v0 analysis."""
    _apply_style()
    plots_dir = Path(plots_dir)
    plots_dir.mkdir(parents=True, exist_ok=True)

    fig = plot_risk_heatmap(pct_df, plots_dir / "pct_change_heatmap.png")
    plt.close(fig)

    fig = plot_scenario_concept(sensitivity_df, plots_dir / "scenario_concept_diagram.png")
    plt.close(fig)

    fig = plot_combined_sensitivity(sensitivity_df, plots_dir / "sensitivity_curves.png")
    plt.close(fig)

    fig = plot_sensitivity_by_surface_type(
        sensitivity_df, plots_dir / "sensitivity_by_surface_type.png"
    )
    plt.close(fig)

    # Box plot for key scenarios
    key_scenarios = ["scenario_000", "scenario_012", "scenario_024"]
    fig, ax = plt.subplots(figsize=(10, 6))
    box_data, labels = [], []
    for sid in key_scenarios:
        if sid in master_summary["scenario_id"].values:
            data = master_summary[master_summary["scenario_id"] == sid]["degree_hours"]
            box_data.append(data.values)
            if sid == "scenario_000":
                labels.append("S000\n(0%, 0%)")
            elif sid == "scenario_012":
                labels.append("S012 - Middle\n(50%, 50%)")
            else:
                labels.append("S024\n(100%, 100%)")
    if box_data:
        bp = ax.boxplot(box_data, tick_labels=labels, patch_artist=True)
        colors = ["#FFB3B3", "#FFFFB3", "#B3FFB3"]
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
        ax.set_ylabel("Degree Hours")
        ax.set_title("Distribution of Tree Degree Hours by Scenario")
        fig.savefig(plots_dir / "scenario_comparison_boxplot.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # Top/bottom bar chart
    fig, ax = plt.subplots(figsize=(12, 6))
    sorted_df = pct_df.sort_values("degree_hours_pct_change")
    plot_df = pd.concat([sorted_df.head(5), sorted_df.tail(5)])
    colors = ["#2ecc71" if x < 0 else "#e74c3c" for x in plot_df["degree_hours_pct_change"]]
    ax.barh(range(len(plot_df)), plot_df["degree_hours_pct_change"], color=colors)
    ax.set_yticks(range(len(plot_df)))
    ax.set_yticklabels(
        [
            f"{row['scenario_id']}\n({row['landscape_ratio']:.0%}, {row['facade_ratio']:.0%})"
            for _, row in plot_df.iterrows()
        ]
    )
    ax.axvline(x=0, color="black", linewidth=0.5)
    ax.set_xlabel("% Change in Degree Hours")
    ax.set_title("Top 5 Best and Worst Scenarios (vs Middle 50%/50%)")
    fig.savefig(plots_dir / "top_scenarios_bar.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    _ = results  # reserved for leaf-temp uncertainty plot in future extension
