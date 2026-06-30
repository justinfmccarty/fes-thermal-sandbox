"""treeheat local UI — Setup · Guide · Run · Results.

Launch from the treeheat package directory:

    streamlit run app/streamlit_app.py

Depends only on treeheat.api and treeheat.project (plus app.background for subprocess launch).
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.screens import guide, results, run_screen, setup
from app.styles import MATERIAL_CSS

st.set_page_config(
    page_title="treeheat",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(MATERIAL_CSS, unsafe_allow_html=True)

if "project_dir" not in st.session_state:
    st.session_state["project_dir"] = ""

st.sidebar.title("treeheat")
st.sidebar.caption("Tree thermal-safety workflow")

page = st.sidebar.radio(
    "Screen",
    ["Setup", "Guide", "Run", "Results"],
    label_visibility="collapsed",
)

project_path: Path | None = None
if st.session_state.get("project_dir"):
    project_path = Path(st.session_state["project_dir"])

if page == "Setup":
    project_path = setup.render_setup(project_path)
    if project_path is not None:
        st.session_state["project_dir"] = str(project_path)
elif page == "Guide":
    guide.render_guide(project_path)
elif page == "Run":
    run_screen.render_run(project_path)
else:
    results.render_results(project_path)

st.sidebar.divider()
if project_path:
    st.sidebar.success(f"Project:\n`{project_path}`")
else:
    st.sidebar.info("No project selected")
