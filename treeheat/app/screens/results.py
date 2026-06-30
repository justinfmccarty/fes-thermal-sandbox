"""Results screen — existing analysis plots + scenario table."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from treeheat import api
from treeheat.project import project_config_path


PLOT_FILES = [
    ("Risk heatmap", "pct_change_heatmap.png"),
    ("Scenario concept", "scenario_concept_diagram.png"),
    ("Sensitivity curves", "sensitivity_curves.png"),
    ("Sensitivity by surface", "sensitivity_by_surface_type.png"),
    ("Scenario boxplot", "scenario_comparison_boxplot.png"),
    ("Top scenarios", "top_scenarios_bar.png"),
]


def render_results(project_dir: Path | None) -> None:
    st.markdown('<div class="material-header">Results</div>', unsafe_allow_html=True)

    if project_dir is None:
        st.warning("Complete Setup first — select a project directory.")
        return

    root = Path(project_dir)
    cfg_path = project_config_path(root)
    if not cfg_path.exists():
        st.error(f"Missing config: {cfg_path}")
        return

    plots_dir = root / "outputs" / "analysis" / "plots"
    master_csv = root / "outputs" / "analysis" / "stress_summary_all_scenarios.csv"

    if not master_csv.exists():
        st.info(
            "No analysis outputs yet. Run the **analyze** stage (or **all**) first."
        )
        return

    try:
        results = api.load_analysis(cfg_path)
    except Exception as exc:
        st.error(f"Could not load analysis: {exc}")
        return

    st.markdown('<div class="material-card">', unsafe_allow_html=True)
    st.subheader("Scenario comparison")
    st.dataframe(
        results.pct_df.sort_values("degree_hours_pct_change"),
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if results.sensitivity_df is not None and not results.sensitivity_df.empty:
        reg = getattr(results.sensitivity_df, "attrs", {}).get("regression", {})
        if reg:
            st.markdown('<div class="material-card">', unsafe_allow_html=True)
            st.subheader("Headline sensitivity")
            cols = st.columns(2)
            albedo = reg.get("risk_albedo", {})
            emiss = reg.get("risk_emissivity", {})
            if albedo:
                cols[0].metric(
                    "Albedo slope (%/unit)",
                    f"{albedo.get('slope', 0):.2f}",
                    help=f"R² = {albedo.get('r2', 0):.3f}",
                )
            if emiss:
                cols[1].metric(
                    "Emissivity slope (%/unit)",
                    f"{emiss.get('slope', 0):.2f}",
                    help=f"R² = {emiss.get('r2', 0):.3f}",
                )
            st.markdown("</div>", unsafe_allow_html=True)

    st.subheader("Plots")
    available = [(label, plots_dir / fname) for label, fname in PLOT_FILES if (plots_dir / fname).exists()]

    if not available:
        st.warning(
            f"No PNG plots in `{plots_dir.relative_to(root)}`. "
            "Re-run analyze with `outputs.save_plots: true` in config."
        )
        return

    for i in range(0, len(available), 2):
        cols = st.columns(2)
        for col, (label, path) in zip(cols, available[i : i + 2]):
            with col:
                st.caption(label)
                st.image(str(path), use_container_width=True)
