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
| [`../../treeheat/`](../../treeheat/) | The v1 working pipeline (Phases 1–6 complete; acceptance gate passed). Config-driven CLI + orchestration core. |
| [`proposed_skeleton/`](proposed_skeleton/) | Retired scaffold pointer only — do not build here. |

**One-line orientation:** the science (in `src_archive/METHODOLOGY.md`) and the result
(in the conference paper) are sound; v1 at `treeheat/` reproduces the paper's numbers
(acceptance gate passed). Remaining work: Stage 2→3 automation spike (Phase 7) and
researcher-facing UI skin (Phase 8).

The three `*_archive/` folders are reference material — not the working tree.
