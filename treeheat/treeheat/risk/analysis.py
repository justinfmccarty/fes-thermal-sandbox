"""Cross-scenario aggregation, ranking, sensitivity analysis, and report generation.

PORT FROM: src_archive/results_analysis.py + src_archive/run_analysis.py (Sections 2-6)
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from treeheat.config import get_config, get_path
from treeheat.risk.metrics import calculate_extended_stress_summary

__all__ = [
    "AnalysisResults",
    "build_scenario_mapping",
    "calculate_all_stress_summaries",
    "calculate_area_weighted_properties",
    "calculate_percent_change",
    "generate_report",
    "load_v0_biophysical_results",
    "run_analysis_pipeline",
    "run_sensitivity_analysis",
]

REFERENCE_SCENARIO = "scenario_012"


def build_scenario_mapping(cfg: dict[str, Any] | None = None) -> pd.DataFrame:
    """Map scenario_id to landscape/facade ratios from config instructions."""
    if cfg is None:
        cfg = get_config()
    instructions = cfg["simulation"]["instructions"]
    scenarios = []
    for idx, instr in enumerate(instructions):
        scenarios.append(
            {
                "scenario_id": f"scenario_{idx:03d}",
                "landscape_ratio": instr[0],
                "facade_ratio": instr[1],
            }
        )
    return pd.DataFrame(scenarios)


def calculate_all_stress_summaries(
    results: dict[str, pd.DataFrame],
    cfg: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Calculate per-tree stress summaries for all scenarios."""
    if cfg is None:
        cfg = get_config()

    scenario_mapping = build_scenario_mapping(cfg)
    all_summaries: list[pd.DataFrame] = []

    for scenario_id, results_df in results.items():
        summary = calculate_extended_stress_summary(results_df, cfg=cfg)
        summary["scenario_id"] = scenario_id

        scenario_info = scenario_mapping[scenario_mapping["scenario_id"] == scenario_id]
        if len(scenario_info) > 0:
            summary["landscape_ratio"] = scenario_info["landscape_ratio"].values[0]
            summary["facade_ratio"] = scenario_info["facade_ratio"].values[0]
        else:
            summary["landscape_ratio"] = np.nan
            summary["facade_ratio"] = np.nan

        all_summaries.append(summary)

    return pd.concat(all_summaries, ignore_index=True)


def calculate_percent_change(
    master_summary: pd.DataFrame,
    reference_scenario: str = REFERENCE_SCENARIO,
) -> pd.DataFrame:
    """Scenario-level percent change relative to the middle (50/50) scenario."""
    middle_data = master_summary[master_summary["scenario_id"] == reference_scenario]
    middle_means = {
        "heat_stress_hours": middle_data["heat_stress_hours"].mean(),
        "degree_hours": middle_data["degree_hours"].mean(),
        "mean_Tleaf_C": middle_data["mean_Tleaf_C"].mean(),
        "max_Tleaf_C": middle_data["max_Tleaf_C"].mean(),
        "mean_MRT_C": middle_data["mean_MRT_C"].mean(),
        "max_MRT_C": middle_data["max_MRT_C"].mean(),
        "mean_Tsurf_C": middle_data["mean_Tsurf_C"].mean(),
        "max_Tsurf_C": middle_data["max_Tsurf_C"].mean(),
    }

    scenario_mapping = build_scenario_mapping()
    pct_changes: list[dict[str, Any]] = []

    for _, scenario in scenario_mapping.iterrows():
        sid = scenario["scenario_id"]
        scenario_data = master_summary[master_summary["scenario_id"] == sid]
        if len(scenario_data) == 0:
            continue

        row: dict[str, Any] = {
            "scenario_id": sid,
            "landscape_ratio": scenario["landscape_ratio"],
            "facade_ratio": scenario["facade_ratio"],
        }

        for metric, middle_val in middle_means.items():
            scenario_mean = scenario_data[metric].mean()
            row[f"{metric}_mean"] = scenario_mean
            if middle_val != 0:
                pct = (scenario_mean - middle_val) / abs(middle_val) * 100
            else:
                pct = 0.0 if scenario_mean == 0 else np.inf
            row[f"{metric}_pct_change"] = pct

        pct_changes.append(row)

    return pd.DataFrame(pct_changes)


def calculate_area_weighted_properties(
    scenario_id: str,
    cfg: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Area-weighted mean albedo and emissivity for a scenario."""
    if cfg is None:
        cfg = get_config()

    material_db_path = get_path("material_database_file", cfg)
    scenario_grid_path = get_path("scenario_grid_materials_file", cfg)

    material_db = pd.read_csv(material_db_path)
    grid_materials = pd.read_csv(scenario_grid_path)
    scenario_materials = grid_materials[grid_materials["scenario_id"] == scenario_id]

    empty_result = {
        "mean_albedo": np.nan,
        "mean_emissivity": np.nan,
        "total_area": 0.0,
        "landscape_albedo": np.nan,
        "landscape_emissivity": np.nan,
        "landscape_area": 0.0,
        "facade_albedo": np.nan,
        "facade_emissivity": np.nan,
        "facade_area": 0.0,
    }

    if len(scenario_materials) == 0:
        return empty_result

    merged = scenario_materials.merge(
        material_db[["material_name", "shortwave_albedo", "thermal_emissivity"]],
        on="material_name",
        how="left",
    )

    def weighted_mean(df: pd.DataFrame, col: str) -> float:
        area = df["area_m2"].sum()
        if area == 0:
            return np.nan
        return float((df[col] * df["area_m2"]).sum() / area)

    total_area = merged["area_m2"].sum()
    if total_area == 0:
        return empty_result

    landscape = merged[merged["ground_or_facade"] == "ground"]
    facade = merged[merged["ground_or_facade"] == "facade"]

    return {
        "mean_albedo": weighted_mean(merged, "shortwave_albedo"),
        "mean_emissivity": weighted_mean(merged, "thermal_emissivity"),
        "total_area": float(total_area),
        "landscape_albedo": weighted_mean(landscape, "shortwave_albedo"),
        "landscape_emissivity": weighted_mean(landscape, "thermal_emissivity"),
        "landscape_area": float(landscape["area_m2"].sum()),
        "facade_albedo": weighted_mean(facade, "shortwave_albedo"),
        "facade_emissivity": weighted_mean(facade, "thermal_emissivity"),
        "facade_area": float(facade["area_m2"].sum()),
    }


def _run_regressions(valid_data: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Linear regressions for risk vs material properties."""
    regression_results: dict[str, dict[str, float]] = {}

    slope_a, intercept_a, r_a, p_a, _ = stats.linregress(
        valid_data["mean_albedo"],
        valid_data["degree_hours_pct_change"],
    )
    regression_results["risk_albedo"] = {
        "slope": float(slope_a),
        "intercept": float(intercept_a),
        "r2": float(r_a**2),
        "p": float(p_a),
    }

    slope_e, intercept_e, r_e, p_e, _ = stats.linregress(
        valid_data["mean_emissivity"],
        valid_data["degree_hours_pct_change"],
    )
    regression_results["risk_emissivity"] = {
        "slope": float(slope_e),
        "intercept": float(intercept_e),
        "r2": float(r_e**2),
        "p": float(p_e),
    }

    slope_ta, intercept_ta, r_ta, p_ta, _ = stats.linregress(
        valid_data["mean_albedo"],
        valid_data["mean_Tsurf_C_pct_change"],
    )
    regression_results["tsurf_albedo"] = {
        "slope": float(slope_ta),
        "intercept": float(intercept_ta),
        "r2": float(r_ta**2),
        "p": float(p_ta),
    }

    valid_landscape = valid_data.dropna(subset=["landscape_albedo", "degree_hours_pct_change"])
    if len(valid_landscape) > 2:
        slope, intercept, r, p, _ = stats.linregress(
            valid_landscape["landscape_albedo"],
            valid_landscape["degree_hours_pct_change"],
        )
        regression_results["risk_landscape_albedo"] = {
            "slope": float(slope),
            "intercept": float(intercept),
            "r2": float(r**2),
            "p": float(p),
        }
        slope, intercept, r, p, _ = stats.linregress(
            valid_landscape["landscape_emissivity"],
            valid_landscape["degree_hours_pct_change"],
        )
        regression_results["risk_landscape_emissivity"] = {
            "slope": float(slope),
            "intercept": float(intercept),
            "r2": float(r**2),
            "p": float(p),
        }

    valid_facade = valid_data.dropna(subset=["facade_albedo", "degree_hours_pct_change"])
    if len(valid_facade) > 2:
        slope, intercept, r, p, _ = stats.linregress(
            valid_facade["facade_albedo"],
            valid_facade["degree_hours_pct_change"],
        )
        regression_results["risk_facade_albedo"] = {
            "slope": float(slope),
            "intercept": float(intercept),
            "r2": float(r**2),
            "p": float(p),
        }
        slope, intercept, r, p, _ = stats.linregress(
            valid_facade["facade_emissivity"],
            valid_facade["degree_hours_pct_change"],
        )
        regression_results["risk_facade_emissivity"] = {
            "slope": float(slope),
            "intercept": float(intercept),
            "r2": float(r**2),
            "p": float(p),
        }

    return regression_results


def run_sensitivity_analysis(
    pct_df: pd.DataFrame,
    cfg: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Sensitivity analysis: risk vs area-weighted albedo and emissivity."""
    if cfg is None:
        cfg = get_config()

    rows: list[dict[str, Any]] = []
    for _, row in pct_df.iterrows():
        sid = row["scenario_id"]
        props = calculate_area_weighted_properties(sid, cfg)
        rows.append(
            {
                "scenario_id": sid,
                "landscape_ratio": row["landscape_ratio"],
                "facade_ratio": row["facade_ratio"],
                "mean_albedo": props["mean_albedo"],
                "mean_emissivity": props["mean_emissivity"],
                "total_area": props["total_area"],
                "landscape_albedo": props["landscape_albedo"],
                "landscape_emissivity": props["landscape_emissivity"],
                "landscape_area": props["landscape_area"],
                "facade_albedo": props["facade_albedo"],
                "facade_emissivity": props["facade_emissivity"],
                "facade_area": props["facade_area"],
                "degree_hours_pct_change": row.get("degree_hours_pct_change", np.nan),
                "mean_Tsurf_C_pct_change": row.get("mean_Tsurf_C_pct_change", np.nan),
                "mean_MRT_C_pct_change": row.get("mean_MRT_C_pct_change", np.nan),
            }
        )

    sensitivity_df = pd.DataFrame(rows)
    valid_data = sensitivity_df.dropna(subset=["mean_albedo", "degree_hours_pct_change"])
    if len(valid_data) > 2:
        sensitivity_df.attrs["regression"] = _run_regressions(valid_data)

    return sensitivity_df


def generate_report(
    pct_df: pd.DataFrame,
    sensitivity_df: pd.DataFrame,
    master_summary: pd.DataFrame,
    output_dir: Path,
    raytracing_dir: Path | None = None,
) -> str:
    """Generate markdown analysis report."""
    if raytracing_dir is None:
        raytracing_dir = get_path("raytracing_results_dir")

    report_lines = [
        "# Tree Stress Analysis Report",
        f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"\nData source: `{raytracing_dir}`",
        "\n## Summary Statistics\n",
        f"- Total scenarios analyzed: {len(pct_df)}",
        f"- Total trees per scenario: {master_summary.groupby('scenario_id').size().iloc[0]}",
        f"- Reference scenario: {REFERENCE_SCENARIO} (50% landscape, 50% facade)",
    ]

    middle = master_summary[master_summary["scenario_id"] == REFERENCE_SCENARIO]
    report_lines.extend(
        [
            "\n### Middle Scenario (50%, 50%) - Reference Conditions\n",
            f"- Mean T_leaf: {middle['mean_Tleaf_C'].mean():.2f}°C",
            f"- Mean MRT: {middle['mean_MRT_C'].mean():.2f}°C",
            f"- Mean Tsurf: {middle['mean_Tsurf_C'].mean():.2f}°C",
            f"- Mean Degree Hours: {middle['degree_hours'].mean():.2f}",
            "\n## Key Findings\n",
            "### Risk Index Changes (Relative to Middle Scenario)\n",
        ]
    )

    risk_col = "degree_hours_pct_change"
    min_row = pct_df.loc[pct_df[risk_col].idxmin()]
    max_row = pct_df.loc[pct_df[risk_col].idxmax()]

    report_lines.extend(
        [
            f"- **Best scenario** (lowest risk vs middle): {min_row['scenario_id']} "
            f"(Landscape: {min_row['landscape_ratio']:.0%}, Facade: {min_row['facade_ratio']:.0%})",
            f"  - Risk change: {min_row[risk_col]:.2f}%",
            f"- **Worst scenario** (highest risk vs middle): {max_row['scenario_id']} "
            f"(Landscape: {max_row['landscape_ratio']:.0%}, Facade: {max_row['facade_ratio']:.0%})",
            f"  - Risk change: {max_row[risk_col]:.2f}%",
            "\n### Sensitivity Analysis\n",
        ]
    )

    if "regression" in sensitivity_df.attrs:
        reg = sensitivity_df.attrs["regression"]
        report_lines.extend(
            [
                "**Risk vs Albedo:**",
                f"- Slope: {reg['risk_albedo']['slope']:.2f} %/unit",
                f"- R²: {reg['risk_albedo']['r2']:.3f}",
                f"- p-value: {reg['risk_albedo']['p']:.4f}",
                "\n**Risk vs Emissivity:**",
                f"- Slope: {reg['risk_emissivity']['slope']:.2f} %/unit",
                f"- R²: {reg['risk_emissivity']['r2']:.3f}",
                f"- p-value: {reg['risk_emissivity']['p']:.4f}",
                "\n**Tsurf vs Albedo:**",
                f"- Slope: {reg['tsurf_albedo']['slope']:.2f} %/unit",
                f"- R²: {reg['tsurf_albedo']['r2']:.3f}",
                f"- p-value: {reg['tsurf_albedo']['p']:.4f}",
            ]
        )

    report_lines.extend(
        [
            "\n## Output Files\n",
            f"- `{output_dir}/stress_summary_all_scenarios.csv`",
            f"- `{output_dir}/pct_change_summary.csv`",
            f"- `{output_dir}/sensitivity_analysis.csv`",
            f"- `{output_dir}/plots/`",
            f"\n**Note**: All comparisons are relative to {REFERENCE_SCENARIO} (50% landscape, 50% facade).",
        ]
    )

    report_text = "\n".join(report_lines)
    output_path = output_dir / "analysis_report.md"
    output_path.write_text(report_text, encoding="utf-8")
    return report_text


def load_v0_biophysical_results(
    cfg: dict[str, Any] | None = None,
    scenario_ids: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Load frozen v0 biophysical result CSVs for fast-tier acceptance."""
    if cfg is None:
        cfg = get_config()

    ref_dir = get_path("v0_reference_dir", cfg)
    if scenario_ids is None:
        n = int(cfg.get("simulation", {}).get("n_scenarios", 25))
        scenario_ids = [f"scenario_{i:03d}" for i in range(n)]

    results: dict[str, pd.DataFrame] = {}
    for scenario_id in scenario_ids:
        path = ref_dir / f"biophysical_results_{scenario_id}.csv"
        if path.exists():
            results[scenario_id] = pd.read_csv(path)
    return results


class AnalysisResults:
    """Container for analysis pipeline outputs."""

    def __init__(
        self,
        master_summary: pd.DataFrame,
        pct_df: pd.DataFrame,
        sensitivity_df: pd.DataFrame,
        biophysical_results: dict[str, pd.DataFrame],
    ):
        self.master_summary = master_summary
        self.pct_df = pct_df
        self.sensitivity_df = sensitivity_df
        self.biophysical_results = biophysical_results

    @property
    def regression(self) -> dict[str, dict[str, float]]:
        return self.sensitivity_df.attrs.get("regression", {})

    @property
    def best_scenario(self) -> str:
        risk_col = "degree_hours_pct_change"
        return str(self.pct_df.loc[self.pct_df[risk_col].idxmin(), "scenario_id"])

    @property
    def worst_scenario(self) -> str:
        risk_col = "degree_hours_pct_change"
        return str(self.pct_df.loc[self.pct_df[risk_col].idxmax(), "scenario_id"])

    @property
    def best_pct_change(self) -> float:
        risk_col = "degree_hours_pct_change"
        return float(self.pct_df.loc[self.pct_df[risk_col].idxmin(), risk_col])

    @property
    def worst_pct_change(self) -> float:
        risk_col = "degree_hours_pct_change"
        return float(self.pct_df.loc[self.pct_df[risk_col].idxmax(), risk_col])


def run_analysis_pipeline(
    biophysical_results: dict[str, pd.DataFrame],
    cfg: dict[str, Any] | None = None,
    output_dir: Path | None = None,
    save_plots: bool = True,
) -> AnalysisResults:
    """Run full analysis: stress summaries, pct change, sensitivity, report, plots."""
    if cfg is None:
        cfg = get_config()

    if output_dir is None:
        output_dir = get_path("analysis_results_dir", cfg)
    output_dir = Path(output_dir)
    plots_dir = output_dir / "plots"
    os.makedirs(plots_dir, exist_ok=True)

    master_summary = calculate_all_stress_summaries(biophysical_results, cfg)
    master_summary.to_csv(output_dir / "stress_summary_all_scenarios.csv", index=False)

    pct_df = calculate_percent_change(master_summary)
    pct_df.to_csv(output_dir / "pct_change_summary.csv", index=False)

    sensitivity_df = run_sensitivity_analysis(pct_df, cfg)
    sensitivity_df.to_csv(output_dir / "sensitivity_analysis.csv", index=False)

    generate_report(pct_df, sensitivity_df, master_summary, output_dir)

    if save_plots:
        try:
            from treeheat.viz import plots as viz_plots

            viz_plots.generate_all_plots(
                pct_df,
                sensitivity_df,
                master_summary,
                biophysical_results,
                plots_dir,
                cfg,
            )
        except ImportError:
            pass

    return AnalysisResults(
        master_summary=master_summary,
        pct_df=pct_df,
        sensitivity_df=sensitivity_df,
        biophysical_results=biophysical_results,
    )
