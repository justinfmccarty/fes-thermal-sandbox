"""Setup screen — project selection, validation checklist, config overrides."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
import yaml

from treeheat import api
from treeheat.config import get_config, reload_config
from treeheat.project import (
    init_project,
    project_config_path,
    read_config_overrides,
    validate_project,
    write_config_overrides,
)


def _status_icon(status: str) -> str:
    return {"ok": "✅", "missing": "❌", "warning": "⚠️"}.get(status, "•")


def render_setup(project_dir: Path | None) -> Path | None:
    st.markdown('<div class="material-header">Setup</div>', unsafe_allow_html=True)
    st.caption("Choose or create an external project directory. Edit run overrides below.")

    col1, col2 = st.columns([3, 1])
    with col1:
        path_str = st.text_input(
            "Project directory",
            value=str(project_dir) if project_dir else "",
            placeholder="/path/to/my_site",
            key="setup_project_path",
        )
    with col2:
        st.write("")
        st.write("")
        if st.button("Use path", use_container_width=True):
            if path_str.strip():
                st.session_state["project_dir"] = str(Path(path_str).expanduser().resolve())

    new_dir = st.text_input("Initialize new project at", placeholder="~/Projects/new_site")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("treeheat init", type="primary", use_container_width=True):
            if not new_dir.strip():
                st.error("Enter a directory path to initialize.")
            else:
                target = Path(new_dir).expanduser().resolve()
                try:
                    report = init_project(target)
                    st.session_state["project_dir"] = str(report.project_dir)
                    st.success(f"Initialized {report.project_dir}")
                except FileExistsError as exc:
                    st.error(str(exc))
    with c2:
        force_init = st.checkbox("Force (non-empty dir)", value=False)

    if force_init and new_dir.strip() and st.button("Force init", use_container_width=True):
        target = Path(new_dir).expanduser().resolve()
        report = init_project(target, force=True)
        st.session_state["project_dir"] = str(report.project_dir)
        st.success(f"Force-initialized {report.project_dir}")

    active = st.session_state.get("project_dir")
    if not active:
        st.info("Select or initialize a project directory to continue.")
        return None

    root = Path(active)
    if not root.is_dir():
        st.error(f"Directory not found: {root}")
        return None

    st.markdown('<div class="material-card">', unsafe_allow_html=True)
    st.subheader("Project checklist")
    report = validate_project(root, check_config=True)
    for item in report.items:
        icon = _status_icon(item.status)
        detail = f" — {item.detail}" if item.detail else ""
        st.markdown(f"{icon} `{item.path}`{detail}")

    if report.config_valid is True:
        st.markdown("✅ **Config validation passed**")
    elif report.config_valid is False:
        st.markdown(f"❌ **Config validation failed:** {report.config_error}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="material-card">', unsafe_allow_html=True)
    st.subheader("Run overrides")
    st.caption("Saved to config/config.yaml — defaults load from the treeheat package.")

    run_cfg = read_config_overrides(root)
    cfg_path = project_config_path(root)
    reload_config(cfg_path)
    merged = get_config(cfg_path)

    engines = api.available_canopy_engines()
    current_engine = run_cfg.get("model", {}).get("canopy_engine", merged["model"]["canopy_engine"])
    engine = st.selectbox("Canopy engine", engines, index=engines.index(current_engine))

    period_options = ["warmest_week", "annual"]
    current_period = run_cfg.get("analysis", {}).get("period_type", merged["analysis"]["period_type"])
    period = st.selectbox(
        "Analysis period",
        period_options,
        index=period_options.index(current_period),
    )

    n_scenarios = int(
        run_cfg.get("simulation", {}).get(
            "n_scenarios", merged["simulation"]["n_scenarios"]
        )
    )
    n_scenarios = st.number_input("Number of scenarios", min_value=1, max_value=25, value=n_scenarios)

    current_accelerad = bool(
        run_cfg.get("simulation", {}).get(
            "use_accelerad", merged["simulation"].get("use_accelerad", False)
        )
    )
    use_accelerad = st.checkbox(
        "Use Accelerad (GPU ray tracing)",
        value=current_accelerad,
        help=(
            "Requires the Accelerad build of Radiance installed and on PATH. "
            "Leave off to use the standard Radiance bundled with treeheat — if "
            "Accelerad is enabled but not found, the run falls back to standard "
            "Radiance automatically."
        ),
    )

    if st.button("Save overrides to config.yaml", type="primary"):
        overrides: dict = {
            "model": {"canopy_engine": engine},
            "analysis": {"period_type": period},
            "simulation": {"n_scenarios": int(n_scenarios), "use_accelerad": bool(use_accelerad)},
        }
        if int(n_scenarios) != 25:
            instructions = merged["simulation"]["instructions"][: int(n_scenarios)]
            overrides["simulation"]["instructions"] = instructions
        write_config_overrides(root, overrides)
        st.success(f"Saved {project_config_path(root)}")

    with st.expander("View config.yaml"):
        st.code(
            yaml.safe_dump(read_config_overrides(root), sort_keys=False),
            language="yaml",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    return root
