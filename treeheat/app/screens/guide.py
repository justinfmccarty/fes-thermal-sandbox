"""Guide screen — project runbook (Grasshopper → treeheat-ready project)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from treeheat.project import project_runbook_path, read_runbook


def render_guide(project_dir: Path | None) -> None:
    st.markdown('<div class="material-header">Guide</div>', unsafe_allow_html=True)
    st.caption("Grasshopper / Honeybee → Radiance export procedure for your project.")

    if project_dir is not None:
        local = project_runbook_path(project_dir)
        if local.is_file():
            st.info(f"Showing project copy: `{local.name}`")
        else:
            st.warning(
                f"No `{local.name}` in this project — showing packaged runbook. "
                "Re-run `treeheat init --force` to copy it locally."
            )
    else:
        st.info("Select a project in **Setup** to view its local runbook copy.")

    try:
        body = read_runbook(project_dir)
    except FileNotFoundError as exc:
        st.error(str(exc))
        return

    st.markdown(body)
