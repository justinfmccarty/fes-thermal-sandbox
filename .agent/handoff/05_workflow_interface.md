# Workflow Interface — Design Note

> **Status:** Design decision, not a build. Records *what* to build, *why*, and the guardrails — so the new team builds it in the right order and doesn't over-scope.
> **Companion:** Recommendation 7 in [`03_consolidation_recommendations.md`](03_consolidation_recommendations.md).
> **One-line:** a local, researcher-facing skin over the orchestration core — for scenario setup, run execution, and basic analysis — built **last**.

---

## 1. The goal, stated plainly

Researchers should be able to set up a material-scenario sweep, launch it, watch it run, and see the basic results **without touching a terminal or a Jupyter notebook**. That is the entire mandate. It is a convenience layer, not a new capability.

## 2. The architectural truth (read this before imagining a UI)

**A UI cannot escape the backend.** Annual Radiance runs are heavy compute that need `pyradiance` and the scene geometry installed on a real machine. A browser cannot run them. Therefore:

- Setup, execution, and analysis all route through the **same Python pipeline** the agents use.
- The interface is **presentation only**. It collects inputs, launches the backend, polls state, and renders outputs.
- This makes the **orchestration core a hard prerequisite** — the UI is built on top of it, never instead of it.

```
┌────────────────────────────┐
│  UI skin (Streamlit)       │   Setup · Run · Results   ← researcher sees this
│  forms · launch · polling  │
└──────────────┬─────────────┘
               │ calls / reads run-state file
┌──────────────▼─────────────┐
│  Orchestration core         │   job spec → graph → runner → provenance
│  (treeheat API + CLI)       │   skip-already-computed · resume · status
└──────────────┬─────────────┘
┌──────────────▼─────────────┐
│  Pipeline (Stages 3–5)      │   radiance · physics(engines) · risk · viz
└────────────────────────────┘
```

If the core is clean (a Python API plus run-state written to disk), the skin is cheap. That is the whole bet.

## 3. The orchestration core (the part that does the work)

Most of this already exists informally inside `MaterialScenarioWorkflow` — the job is to **formalise** it, not invent it.

- **Job spec** — a YAML/JSON batch: which scenarios, which period, which engine. Validated on load.
- **Runner** — builds the scenario dependency graph; **skips already-computed work** (content-addressed by a hash of config + inputs); runs only what's missing.
- **Provenance** — each output records the config + code version that produced it, so a result is auditable and re-runnable deterministically.
- **Run-state on disk** — a small JSON the UI (or `treeheat status`) polls: per-scenario `pending / running / done / failed`, timestamps, output paths.

This core is valuable on its own — agents benefit from it with no UI at all (it is also Tier 1 in the original discussion).

## 4. The skin: three screens, and nothing more

Recommended form factor: a **local Streamlit app** (`streamlit run app.py`). Pure Python, no JavaScript, localhost only — no auth, no deployment, no multi-user. **Gradio** is the simpler, more form-like alternative; pick it if the results screen doesn't need to feel like a dashboard.

1. **Setup** — choose materials, define the naturalness sweep (the 5×5 landscape/facade grid), pick the period (annual / warmest-week). Output: a validated job spec. *No free-form code entry.*
2. **Run** — a launch button; live status read from the run-state file; resume / skip-already-computed surfaced as toggles. *Does not block on the run.*
3. **Results** — the plots that **already exist** (albedo & emissivity sensitivity, scenario ranking, per-tree distributions) plus a scenario-comparison table.

## 5. The one real engineering risk — the job model

Long sweeps (annual Radiance = hours) **must not run in the UI process.** Design from day one:

- The UI launches the run as a **background process** (subprocess / job runner) that survives the UI session — close the laptop lid, the run continues.
- The UI **polls the run-state file**; it never holds the computation.
- Failures are captured to the run-state with enough detail to resume.

Get this wrong and you ship a UI that freezes on every run. Everything else here is forms and plots.

## 6. Guardrails — where this goes wrong

This is the **most likely part of the whole project to over-build.** Hard limits:

- A workflow GUI **does not** help reproduce the paper's numbers. The science port does. Interface time is physics time not spent.
- **Three screens.** No scenario IDE, no live geometry editor, no general BI tool, no user accounts.
- **Reuse existing plots.** Do not build new visualisation for the UI; surface what `viz/` already produces.
- If it can't stay **a weekend on top of a working core**, it is out of scope for now.

## 7. Build order (non-negotiable)

```
physics port  →  acceptance gate passes  →  orchestration core + CLI  →  UI skin
```

The UI is **step 8** in the sequencing of [`03_consolidation_recommendations.md`](03_consolidation_recommendations.md). It is deliberately last: a UI built before the pipeline runs is a UI with nothing to drive.

## 8. Where it lands in the skeleton

When the time comes, add (not now — these are pointers):

- `treeheat/orchestration/` — job spec, runner, provenance, run-state. The CLI (`treeheat/cli.py`) is its first consumer.
- `app/` (or `treeheat/ui/`) — the Streamlit skin. Depends only on the orchestration API, never on the pipeline modules directly.

Keeping the skin in its own package enforces the "presentation only" boundary: if the UI ever needs to import a physics module, that's the signal it's overreaching.
