# v1 Build Prompts — Sequenced Planning Prompts for Cursor

**What this is.** A sequence of copy-paste prompts for an agent (in Cursor) that has this
repo open. Each prompt produces a **written plan** for one phase of building v1 — it does
**not** write implementation code. You review the plan, adjust, approve, *then* tell the
agent to execute it. This mirrors the project's working rule: stress-test and plan before
editing.

**How to use.**
1. Drop the "Project Rules" block below into Cursor's rules (`.cursor/rules` or project
   settings) so the principles persist across every chat.
2. Run the phase prompts **in order**. Each is self-contained; paste one, get a plan, review.
3. Plans are written to `.agent/local_memory/plans/NN_<phase>.md`. Approve before the agent
   touches code.
4. The meta-objective and acceptance gate are the same for the whole sequence:
   **reproduce the v0 paper's headline numbers** (albedo sensitivity ≈ +61 %/unit, R²≈0.87;
   emissivity ≈ −194 %/unit) before any new science. That gate is "v1 works."

**Orientation for the agent (and you):** start at `.agent/handoff/README.md`. The repo is
v0/reference; v1 is built clean per `.agent/handoff/03_consolidation_recommendations.md`.

---

## Project Rules (paste into Cursor rules — persistent context)

```
You are helping build v1 of a tree thermal-safety simulation pipeline. This repo is v0:
archive/reference only, READ-ONLY. v1 is built clean per the handoff in .agent/handoff/.

Non-negotiable principles:
1. PLAN FIRST. For any phase, produce a written plan and STOP for human review. Do not
   write implementation code until the plan is approved.
2. The acceptance gate defines "done": v1 must reproduce the v0 paper's numbers
   (albedo sensitivity ~ +61 %/unit R^2~0.87; emissivity ~ -194 %/unit) before new science.
3. config is the single source of truth. No hardcoded paths or model defaults in code.
   All parameters resolve through one config loader; validate config loudly at startup.
4. The canopy model is a PLUGGABLE ENGINE. Li 2023 CEB is the current default behind a
   CanopyEngine interface; a future swap must be one new file + one config line. The
   integrator never imports a concrete canopy model.
5. Preserve the v0 module layering (config -> io -> radiance -> physics -> risk -> viz).
6. Do not load archive directories wholesale (~1.5 GB, mostly data). Use
   .agent/handoff/04_archive_map.md to open only the file you need.
7. Do not over-build. Especially the workflow UI: three screens max, reuse existing plots,
   it rides on the orchestration core. Interface time is not physics time.
8. Treat outputs/ as generated and git-ignored, never committed.

When you produce a plan, include: objective, files to create/modify, key design decisions
with rationale, risks + mitigations, acceptance criteria for the phase, and an explicit
"open questions for the human" list. Write the plan to .agent/local_memory/plans/.
```

---

## Phase 0 — Orientation & v1 roadmap

```
Read the full handoff set in .agent/handoff/ (README, 01–05) and skim the v0 orientation
files it points to (src_archive/METHODOLOGY.md, src_archive/config.yaml,
src_archive/analysis_outputs/analysis_report.md). Do NOT read archive data directories.

Produce a single roadmap document that:
- restates the v1 objective and the acceptance gate in your own words,
- lists the build phases (from 03_consolidation_recommendations.md sequencing) with their
  dependencies, and what "done" means for each,
- flags the top 3 risks to reaching the acceptance gate,
- lists open questions you need me to answer before Phase 1.

Do not write any code. Write the roadmap to .agent/local_memory/plans/00_roadmap.md and stop.
```

---

## Phase 1 — Skeleton, config, and validation

```
Goal: stand up the clean v1 package and the config backbone.

Read: .agent/handoff/proposed_skeleton/ (entire structure, especially treeheat/config.py,
cli.py, and the engines/ stubs) and src_archive/config.yaml + src_archive/config_locator.py
for what the config must carry.

Produce a plan to:
- adopt or refine the proposed_skeleton as the v1 package,
- implement the config loader (defaults.yaml overridden by config.yaml, relative paths
  resolved against the config dir) and a validate_config() that fails loudly,
- define the project layout, packaging (pyproject), and a minimal test harness.

Constraints: config is the single source of truth (Rule 3). Preserve module layering (Rule 5).
Acceptance criteria for the phase: `validate_config()` passes on a complete config and fails
with a clear error on a missing key or path; package imports cleanly; engine registry resolves.

Do not write code yet. Write the plan to .agent/local_memory/plans/01_skeleton_config.md and stop.
```

---

## Phase 2 — Port reference data (databases + methodology)

```
Goal: bring the validated, low-risk reference material into v1.

Read: src_archive/tree_species_database.csv, src_archive/root_material_database.csv (note the
schemas and citation columns), and src_archive/METHODOLOGY.md (the physics spec — inherit, do
not rewrite). Cross-check schema notes in .agent/handoff/02_codebase_guide.md §4.

Produce a plan to:
- place the databases and METHODOLOGY into v1's data/ and docs,
- define typed loaders for the two databases (carry schemas forward unchanged),
- record any schema cleanups you recommend (and why), without changing the science.

Acceptance criteria: loaders return validated, typed records; a schema-conformance test
guards the CSVs; METHODOLOGY is referenced as the authoritative spec, not duplicated.

Do not write code yet. Write the plan to .agent/local_memory/plans/02_reference_data.md and stop.
```

---

## Phase 3 — Physics behind the engine interface

```
Goal: port the biophysics with the canopy model as a pluggable engine.

Read: src_archive/biophysical_tree_stress.py (the integrator), src_archive/li2023_ceb_model.py
(current engine), src_archive/leaf_energy_balance.py (legacy engine), and the physics modules
ground_temperature.py, surface_energy_balance.py, soil_moisture.py, upwelling_calculator.py.
Read the engine stubs in .agent/handoff/proposed_skeleton/treeheat/physics/engines/.

Produce a plan to:
- finalize the CanopyEngine interface from the TWO real engines (CEB + legacy), so it's
  grounded, not speculative,
- port the physics modules and wire the integrator to call engines.get_engine(config),
- register li2023_ceb as default and legacy_leaf as a cross-check.

Constraints: integrator must NOT import a concrete canopy model (Rule 4). If the legacy
solver won't fit the interface cleanly, design around CEB and adapt legacy — and say so.
Acceptance criteria: a single-tree, single-hour CEB solve runs and matches the v0 result for
the same inputs; swapping to legacy_leaf is a one-line config change.

Do not write code yet. Write the plan to .agent/local_memory/plans/03_physics_engines.md and stop.
```

---

## Phase 4 — Radiance, risk, analysis, and the ACCEPTANCE GATE

```
Goal: complete the back-half pipeline and prove the port reproduces the paper.

Read: src_archive/radiance.py (2-phase DDS via pyradiance), src_archive/risk_metrics.py,
src_archive/results_analysis.py, src_archive/plots.py + plot_formatting.py, and
src_archive/analysis_outputs/analysis_report.md (the target numbers).

Produce a plan to:
- port the Radiance runner, risk metrics, cross-scenario analysis, and plots,
- assemble the end-to-end run for the 25-scenario sweep,
- implement the ACCEPTANCE TEST that reproduces the paper's headline numbers
  (albedo ~ +61 %/unit R^2~0.87; emissivity ~ -194 %/unit; best/worst scenarios),
- define tolerances and what counts as pass/fail.

This is the phase that defines "v1 works." Acceptance criteria: the acceptance test passes
within stated tolerance against the v0 results.

Do not write code yet. Write the plan to .agent/local_memory/plans/04_pipeline_acceptance.md and stop.
```

---

## Phase 5 — CLI and orchestration core

```
Goal: one config-driven entry point + the run machinery the UI will later sit on.

Read: src_archive/run_analysis.py (the clean canonical entry point) and
src_archive/material_scenario_workflow.py (the engine class with the run logic), plus
.agent/handoff/05_workflow_interface.md §3 (orchestration core) and Recommendation 1 in
.agent/handoff/03_consolidation_recommendations.md.

Produce a plan to:
- implement cli.py with subcommands (raytrace | biophysics | analyze | all),
- formalize the orchestration core: a job spec (batch of scenarios), a runner that skips
  already-computed work (content-addressed by config+input hash), provenance per output,
  and a run-state file on disk,
- retire the v0 scripts (workflow.py, workflow_analysis.py, example_usage.py) — preserve the
  25-scenario generation logic first,
- keep a thin Python API the notebooks/UI can import.

Acceptance criteria: `treeheat run all` reproduces the acceptance test; re-running skips
completed scenarios; every output carries provenance; run-state is machine-readable.

Do not write code yet. Write the plan to .agent/local_memory/plans/05_cli_orchestration.md and stop.
```

---

## Phase 6 — Data-retention decision (human-led)

```
Goal: decide what v0 simulation data v1 keeps, and how.

Read: .agent/handoff/03_consolidation_recommendations.md Recommendation 5, and
.agent/handoff/04_archive_map.md (the "large generated outputs" table with sizes).

This is a research-data decision for the human, not an engineering one. Produce a short
decision memo that lays out the options (keep one canonical result set / move large outputs
out of git via LFS or DVC / regenerate-on-demand), with the compute-vs-disk tradeoff for
each, and a recommendation — but leave the final choice to me. Include the .gitignore and
data-layout changes each option implies.

Do not change anything. Write the memo to .agent/local_memory/plans/06_data_retention.md and stop.
```

---

## Phase 7 — Stage 2→3 automation spike (research, not a guarantee)

```
Goal: scope (don't build) the Rhino/Grasshopper -> Radiance export bridge.

Read: .agent/handoff/03_consolidation_recommendations.md Recommendation 6,
.agent/handoff/01_project_description.md §2 (the Stage 2->3 seam), and inspect
model_archive/ (the .gh definition, .3dm, svf/) WITHOUT loading large binaries.

Produce a research-spike plan that:
- describes the current manual export and exactly where it's fragile,
- evaluates candidate automation paths (Honeybee/Ladybug export, rhino3dm,
  compute.rhino3d, headless Grasshopper) with feasibility and licensing caveats,
- proposes a small, bounded experiment to test the most promising path,
- states clearly that this is a spike with an uncertain outcome, not a committed deliverable.

Do not write code yet. Write the plan to .agent/local_memory/plans/07_stage2_3_spike.md and stop.
```

---

## Phase 8 — Workflow interface (LAST, thin skin only)

```
Goal: a researcher-facing UI for setup, execution, and basic analysis — built on the
orchestration core from Phase 5.

Read: .agent/handoff/05_workflow_interface.md in full (this is the design spec).

Produce a plan for a LOCAL Streamlit app with exactly three screens (Setup / Run / Results),
that:
- routes everything through the Phase 5 orchestration API (presentation only; the UI must
  not import physics modules),
- runs long simulations as BACKGROUND processes that survive the UI session, with the UI
  polling the run-state file (design this job model first — it's the only real risk),
- reuses the existing plots for the Results screen; adds no new visualization.

Hard guardrails (Rule 7): three screens, no scenario IDE, no BI tool, no auth/deployment.
If it can't be a thin skin over a working core, it's out of scope.

Do not write code yet. Write the plan to .agent/local_memory/plans/08_workflow_ui.md and stop.
```

---

## Sequencing at a glance

```
0 Roadmap ─► 1 Skeleton+config ─► 2 Reference data ─► 3 Physics+engines ─►
4 Pipeline + ACCEPTANCE GATE ─► 5 CLI + orchestration ─► 6 Data retention ─►
7 Stage 2→3 spike ─► 8 Workflow UI (last)
```

Phase 4 is the gate. Nothing past it ships new science until the paper's numbers reproduce.
Phases 6–8 can be reordered around your priorities; 8 depends on 5. Keep each phase
plan-first: review the plan in `.agent/local_memory/plans/` before the agent writes code.
