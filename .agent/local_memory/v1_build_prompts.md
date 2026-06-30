# v1 Build Prompts — Sequenced Plan-Mode Prompts for Cursor

**What this is.** A sequence of copy-paste prompts for building v1 in Cursor, one phase at
a time. Each prompt is written for **plan mode**: you paste it, Cursor builds a plan and
**reasons with you** about the best course before doing anything, you refine and approve,
it executes, and then it writes a **memory record** of what actually happened. Plan mode is
the human review gate — there's no artificial "stop and wait."

**How to use.**
1. Paste the "Project Rules" block below into Cursor's rules (`.cursor/rules` or project
   settings) so the principles + memory convention persist across every chat.
2. Run the phases **in order**, each in a **fresh chat** (clean context per phase — the
   handoff makes each agent self-orienting from cold).
3. Paste the phase prompt with plan mode on. Discuss and refine the plan. Approve. Let it
   execute. Confirm the memory record was written.
4. The meta-objective and acceptance gate hold for the whole sequence: **reproduce the v0
   paper's headline numbers** (albedo sensitivity ≈ +61 %/unit, R²≈0.87; emissivity ≈
   −194 %/unit) before any new science. That gate is "v1 works."

**Status (as of this writing):** Phases 0–6 (the backend + API) are **complete**. Only
**Phase 8** (the user-facing project + UI layer) remains. Phase 7 has been retired and folded
into Phase 8. The Phase 0–6 prompts are kept below as a record of how the backend was built.

**Orientation for the agent (and you):** start at `.agent/handoff/README.md`. The repo is
v0/reference; v1 is built clean per `.agent/handoff/03_consolidation_recommendations.md`.

---

## Memory records — naming convention

After each phase completes, the agent writes **one Markdown file** to
`.agent/local_memory/`:

```
YYYYMMDD-HHMM_phaseNN_<slug>.md
e.g.  20260629-1430_phase01_skeleton-config.md
```

- **Datetime prefix** → chronological sort and no collisions across re-runs of a phase.
- **Contents:** what was built; key decisions + rationale; **deviations from the plan**
  (the most valuable part — plans drift during execution); test / acceptance status; open
  follow-ups for the next phase.
- **Index:** append a one-line pointer to `.agent/local_memory/INDEX.md`, e.g.
  `- [20260629-1430] Phase 1 — skeleton+config: validate_config passing, engine registry resolves.`

---

## Project Rules (paste into Cursor rules — persistent context)

```
You are helping build v1 of a tree thermal-safety simulation pipeline. This repo is v0:
archive/reference only, READ-ONLY. v1 is built clean per the handoff in .agent/handoff/.

Workflow:
1. PLAN MODE FIRST. Build a plan and reason with the human about the best approach before
   executing. Do not start implementing until the plan is approved. The human review
   happens in plan mode — that is the gate.
2. AFTER execution, ALWAYS write a memory record (do not skip this once the code works):
   one file at .agent/local_memory/YYYYMMDD-HHMM_phaseNN_<slug>.md capturing what was built,
   key decisions, DEVIATIONS from the plan, and test/acceptance status; append a one-line
   entry to .agent/local_memory/INDEX.md.

Non-negotiable principles:
3. The acceptance gate defines "done": v1 must reproduce the v0 paper's numbers
   (albedo sensitivity ~ +61 %/unit R^2~0.87; emissivity ~ -194 %/unit) before new science.
4. config is the single source of truth. No hardcoded paths or model defaults in code.
   All parameters resolve through one config loader; validate config loudly at startup.
5. The canopy model is a PLUGGABLE ENGINE. Li 2023 CEB is the current default behind a
   CanopyEngine interface; a future swap must be one new file + one config line. The
   integrator never imports a concrete canopy model.
6. Preserve the v0 module layering (config -> io -> radiance -> physics -> risk -> viz).
7. Do not load archive directories wholesale (~1 GB+, mostly data). Use
   .agent/handoff/04_archive_map.md to open only the file you need.
8. Do not over-build. Especially the workflow UI: three screens max, reuse existing plots,
   it rides on the orchestration core. Interface time is not physics time.
9. Treat outputs/ as generated and git-ignored, never committed.
10. A "project" is an EXTERNAL working directory (geometry, config, scenarios, outputs) that
   lives OUTSIDE the repo and is never git-tracked. Code takes project location as a
   PARAMETER — never a repo-relative assumption. defaults.yaml ships IN the package; a
   project's config.yaml overlays it. The in-repo v0 data is only the acceptance-test fixture.
```

---

## Phase 0 — Orientation & v1 roadmap

```
Read the full handoff set in .agent/handoff/ (README, 01–05) and skim the v0 orientation
files it points to (src_archive/METHODOLOGY.md, src_archive/config.yaml,
src_archive/analysis_outputs/analysis_report.md). Do NOT read archive data directories.

In plan mode, work through a v1 roadmap WITH me: restate the objective and the acceptance
gate in your own words; lay out the build phases (from 03_consolidation_recommendations.md
sequencing) with their dependencies and what "done" means for each; flag the top 3 risks to
reaching the acceptance gate; and surface the open questions you need me to answer before
Phase 1. Reason with me until we agree — don't just emit a document.

Once we've agreed, write the roadmap as a memory record:
.agent/local_memory/YYYYMMDD-HHMM_phase00_roadmap.md, and add an INDEX.md entry.
```

---

## Phase 1 — Skeleton, config, and validation

```
Build a plan to stand up the clean v1 package and the config backbone.

Read first: .agent/handoff/proposed_skeleton/ (whole structure, especially
treeheat/config.py, cli.py, and the engines/ stubs) and src_archive/config.yaml +
src_archive/config_locator.py for what the config must carry.

The plan should cover: adopting/refining the proposed_skeleton as the v1 package;
implementing the config loader (defaults.yaml overridden by config.yaml, relative paths
resolved against the config dir) and a validate_config() that fails loudly; the project
layout, packaging (pyproject), and a minimal test harness.

Constraints: config is the single source of truth; preserve module layering.
Done = validate_config() passes on a complete config and fails with a clear error on a
missing key/path; package imports cleanly; engine registry resolves.

After the plan is executed and complete, write a memory record to
.agent/local_memory/YYYYMMDD-HHMM_phase01_skeleton-config.md (what was built, key decisions,
deviations from the plan, test status) and add an INDEX.md entry.
```

---

## Phase 2 — Port reference data (databases + methodology)

```
Build a plan to bring the validated, low-risk reference material into v1.

Read first: src_archive/tree_species_database.csv, src_archive/root_material_database.csv
(note the schemas and citation columns), src_archive/METHODOLOGY.md (the physics spec —
inherit, do not rewrite), and schema notes in .agent/handoff/02_codebase_guide.md §4.

The plan should cover: placing the databases and METHODOLOGY into v1's data/ and docs;
typed loaders for the two databases (carry schemas forward unchanged); any schema cleanups
you recommend (and why), without changing the science.

Constraints: do not alter the physics or the database semantics.
Done = loaders return validated, typed records; a schema-conformance test guards the CSVs;
METHODOLOGY is referenced as authoritative, not duplicated.

After execution, write a memory record to
.agent/local_memory/YYYYMMDD-HHMM_phase02_reference-data.md and add an INDEX.md entry.
```

---

## Phase 3 — Physics behind the engine interface

```
Build a plan to port the biophysics with the canopy model as a pluggable engine.

Read first: src_archive/biophysical_tree_stress.py (the integrator),
src_archive/li2023_ceb_model.py (current engine), src_archive/leaf_energy_balance.py (legacy
engine), the physics modules (ground_temperature.py, surface_energy_balance.py,
soil_moisture.py, upwelling_calculator.py), and the engine stubs in
.agent/handoff/proposed_skeleton/treeheat/physics/engines/.

The plan should cover: finalizing the CanopyEngine interface from the TWO real engines
(CEB + legacy) so it's grounded, not speculative; porting the physics modules and wiring the
integrator to call engines.get_engine(config); registering li2023_ceb as default and
legacy_leaf as a cross-check.

Constraints: the integrator must NOT import a concrete canopy model. If the legacy solver
won't fit the interface cleanly, design around CEB and adapt legacy — and say so in the plan.
Done = a single-tree, single-hour CEB solve runs and matches the v0 result for the same
inputs; swapping to legacy_leaf is a one-line config change.

After execution, write a memory record to
.agent/local_memory/YYYYMMDD-HHMM_phase03_physics-engines.md and add an INDEX.md entry.
```

---

## Phase 4 — Radiance, risk, analysis, and the ACCEPTANCE GATE

```
Build a plan to complete the back-half pipeline and prove the port reproduces the paper.

Read first: src_archive/radiance.py (2-phase DDS via pyradiance), src_archive/risk_metrics.py,
src_archive/results_analysis.py, src_archive/plots.py + plot_formatting.py, and
src_archive/analysis_outputs/analysis_report.md (the target numbers).

The plan should cover: porting the Radiance runner, risk metrics, cross-scenario analysis,
and plots; assembling the end-to-end 25-scenario sweep; implementing the ACCEPTANCE TEST that
reproduces the paper's headline numbers (albedo ~ +61 %/unit R^2~0.87; emissivity ~
-194 %/unit; best/worst scenarios); and defining tolerances and pass/fail.

This phase defines "v1 works."
Done = the acceptance test passes within stated tolerance against the v0 results.

After execution, write a memory record to
.agent/local_memory/YYYYMMDD-HHMM_phase04_pipeline-acceptance.md — and state the acceptance-
gate result explicitly (pass/fail + numbers) — then add an INDEX.md entry.
```

---

## Phase 5 — CLI and orchestration core

```
Build a plan for one config-driven entry point plus the run machinery the UI will later sit on.

Read first: src_archive/run_analysis.py (the clean canonical entry point),
src_archive/material_scenario_workflow.py (the engine class with the run logic),
.agent/handoff/05_workflow_interface.md §3 (orchestration core), and Recommendation 1 in
.agent/handoff/03_consolidation_recommendations.md.

The plan should cover: cli.py with subcommands (raytrace | biophysics | analyze | all);
formalizing the orchestration core (a job spec = batch of scenarios; a runner that skips
already-computed work, content-addressed by config+input hash; provenance per output; a
run-state file on disk); retiring the v0 scripts (workflow.py, workflow_analysis.py,
example_usage.py) after preserving the 25-scenario generation logic; and a thin Python API
the notebooks/UI can import.

Constraints: config is the single source of truth; outputs/ stays git-ignored.
Done = `treeheat run all` reproduces the acceptance test; re-running skips completed
scenarios; every output carries provenance; run-state is machine-readable.

After execution, write a memory record to
.agent/local_memory/YYYYMMDD-HHMM_phase05_cli-orchestration.md and add an INDEX.md entry.
```

---

## Phase 6 — Data-retention decision (human-led)

```
Build a plan (really a decision memo) for what v0 simulation data v1 keeps, and how.

Read first: .agent/handoff/03_consolidation_recommendations.md Recommendation 5, and
.agent/handoff/04_archive_map.md (the "large generated outputs" table with sizes).

This is a research-data decision for the human, not an engineering one. In plan mode, lay
out the options (keep one canonical result set / move large outputs out of git via LFS or
DVC / regenerate-on-demand) with the compute-vs-disk tradeoff for each, and a recommendation
— but leave the final choice to me. Include the .gitignore and data-layout changes each
option implies. Do not change data without my decision.

After we decide, write the decision as a memory record to
.agent/local_memory/YYYYMMDD-HHMM_phase06_data-retention.md and add an INDEX.md entry.
```

---

## Phase 8 — Project creation + UI (the user-facing layer)

> Note: the former Phase 7 (Stage 2→3 export automation) is folded in here. Automating the
> Rhino/Grasshopper → Radiance export is explicitly OUT of scope — the modeling stays
> manual by design. What survives from it is a *documented runbook* for the manual export
> and the *project-layout contract* that lets a hand-built export drop into the tool.

```
Build a plan for the user-facing layer: how a user creates a new project AND runs/analyses
it through a UI. Keep TWO layers distinct — do not let them blur:

  (A) PROJECT LAYER (core/CLI — not UI):
      - `treeheat init <dir>`: scaffold an EXTERNAL project directory (a config.yaml stub
        overlaying the package-shipped defaults.yaml, plus the expected sub-dirs for Radiance
        inputs / outputs / run-state).
      - The project-layout CONTRACT: what files/dirs treeheat expects to find in a project.
      - A short RUNBOOK documenting the manual Grasshopper → Radiance export that produces a
        treeheat-ready project (no automation — just the reliable manual procedure).
  (B) UI LAYER (thin skin):
      - a LOCAL Streamlit app, three screens (Setup / Run / Results) that operate on a project
        dir by CALLING the project layer + the Phase 5 orchestration API.

START by reconciling with what Phase 5 actually shipped: read the Phase 5 code and its memory
record and define `init`/layout to MATCH the orchestration's existing assumptions about where
projects, outputs, and run-state live — do not invent a contract that contradicts it.

Read first: .agent/handoff/05_workflow_interface.md (UI design spec), the Phase 5 memory
record + orchestration code, and .agent/handoff/01_project_description.md §2 (the manual
Stage 2→3 seam, for the runbook).

Constraints: `treeheat init` and layout logic live in the CORE/CLI, callable with no UI —
the UI calls them, never owns them. A project is an EXTERNAL dir; its outputs are never
git-tracked. UI = three screens, reuse existing plots, no scenario IDE / BI tool / auth.
Done = `treeheat init` scaffolds a valid external project; the runbook takes a user from a
GH model to a treeheat-ready project; the UI runs that project end-to-end (Setup writes a
valid job spec, a run launches in the background and survives a UI refresh, Results renders
from existing outputs).

Capstone validation: run a NEW user's real project through this layer end-to-end — that is
the generalization test (does the external-project model hold on a fresh case), complementary
to Phase 4's reproduction gate.

After execution, write a memory record to
.agent/local_memory/YYYYMMDD-HHMM_phase08_project-and-ui.md and add an INDEX.md entry.
```

---

## Sequencing at a glance

```
BACKEND + API (Phases 0–6, complete)
0 Roadmap ─► 1 Skeleton+config ─► 2 Reference data ─► 3 Physics+engines ─►
4 Pipeline + ACCEPTANCE GATE ─► 5 CLI + orchestration ─► 6 Data retention

USER-FACING LAYER (remaining)
8 Project creation + UI   (former Phase 7 export-automation folded in; export stays manual)
```

Two-part model: Phases 0–6 built the backend + API; Phase 8 is the user-facing project
workflow. Phase 4 was the reproduction gate (paper's numbers). Phase 8 carries the
complementary generalization test (a new user's real project, end-to-end). Phase 7 is
retired — its useful residue (export runbook + project-layout contract) lives in Phase 8.
Each phase: plan mode to agree the approach, execute, then a dated memory record in
`.agent/local_memory/`.