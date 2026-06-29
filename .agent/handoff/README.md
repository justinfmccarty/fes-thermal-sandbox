# Thermal Sandbox — Handoff

Start here. This folder is the orientation layer for the **agent team building v1** of
the tree thermal-safety project from the v0 archive (and any human lead reviewing it).

| Read | For |
|------|-----|
| [`01_project_description.md`](01_project_description.md) | What the project is, the 5-stage pipeline, the science, and which stages exist as code vs. gaps. |
| [`02_codebase_guide.md`](02_codebase_guide.md) | What the existing `src_archive/` code is, the canonical run path, and what to ignore. |
| [`03_consolidation_recommendations.md`](03_consolidation_recommendations.md) | How to turn the accreted archive into a tight pipeline. Recommendations with counter-considerations. |
| [`04_archive_map.md`](04_archive_map.md) | Token-cheap index: file → "look here when…". Read before opening anything in the archives. |
| [`05_workflow_interface.md`](05_workflow_interface.md) | Design note for the researcher-facing workflow UI: a thin Streamlit skin over an orchestration core, built last. |
| [`proposed_skeleton/`](proposed_skeleton/) | A clean placeholder repo to build the new pipeline into. Stubs only; pluggable canopy engine; one entry point. |

**One-line orientation:** the science (in `src_archive/METHODOLOGY.md`) and the result
(in the conference paper) are sound; the job is to rebuild the back-half pipeline
(Radiance → biophysics → risk) into the skeleton, reproduce the paper's numbers as the
acceptance gate, then extend toward the missing front end (photogrammetry → Rhino).

The three `*_archive/` folders are reference material — not the working tree.
