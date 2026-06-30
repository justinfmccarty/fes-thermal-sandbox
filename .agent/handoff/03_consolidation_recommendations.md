# Consolidation Recommendations

> **Purpose:** Turn the working-but-accreted `src_archive/` into a tighter, automatable pipeline.
> **Companion:** the clean structure is implemented at [`../../treeheat/`](../../treeheat/) (Phases 1–6 complete). The retired scaffold pointer is at [`proposed_skeleton/`](proposed_skeleton/).
> **Framing:** these are *recommendations to stress-test*, not orders. Each carries a rationale and a counter-consideration so the new team can disagree well.

---

## The core diagnosis

The science is sound and the modules are cleanly layered. The mess is in three specific, fixable places:

1. **Five overlapping orchestration scripts** with no signposted canonical path.
2. **Hardcoded absolute paths** (`/Users/jmccarty/Nextcloud/...`) that `config.yaml` was meant to eliminate but never fully did.
3. **~12 one-off scaffolding scripts** living in the main namespace, indistinguishable from real modules.

None of these touch the physics. Consolidation is mostly **deletion and reorganization**, not rewriting.

---

## Recommendation 1 — One entry point, config-driven

**Problem.** `run_analysis.py`, `material_scenario_workflow.py`, `workflow.py`, `workflow_analysis.py`, and `example_usage.py` all look runnable. Three carry hardcoded paths and inline scenario definitions. A newcomer cannot tell which to trust.

**Recommendation.** Collapse to a **single CLI** (`cli.py`) with explicit sub-commands, all parameters from `config.yaml`:

```
treeheat run raytrace   --config config.yaml      # Phase 1 (Stage 3)
treeheat run biophysics --config config.yaml      # Stage 4
treeheat run analyze    --config config.yaml      # Stage 5
treeheat run all        --config config.yaml      # full pipeline
```

Keep the proven internals of `MaterialScenarioWorkflow` and `run_analysis.py` *behind* this CLI. Delete `workflow.py`, `workflow_analysis.py`, `example_usage.py` (preserve the scenario-generation logic from `workflow_analysis.py` first — it encodes the 25-scenario sweep).

**Counter-consideration.** Notebooks (`04`, `05`) are genuinely useful for exploration. Don't force everything through the CLI — keep a thin Python API the notebooks can import. The CLI is for *reproducible runs*, the API for *exploration*.

---

## Recommendation 2 — Make the canopy model a pluggable engine

**Problem.** `li2023_ceb_model.py` (current) and `leaf_energy_balance.py` (legacy) coexist with no formal contract between them. You confirmed the CEB model is a **current drop-in, not a permanent commitment** — a future team may swap it.

**Recommendation.** Define a small **engine interface** and register implementations behind it:

```
physics/engines/
  base.py          # CanopyEngine ABC: solve(state) -> leaf_temperature, fluxes
  li2023_ceb.py    # current default, registered as "li2023_ceb"
  legacy_leaf.py   # prior engine, registered as "legacy_leaf"
```

Selection lives in config:

```yaml
model:
  canopy_engine: li2023_ceb     # swap here, nowhere else
```

The integrator (`biophysical_tree_stress`) calls `engine.solve(...)` and never imports a concrete model. A future engine swap becomes **one new file + one config line**, with no changes to the integrator, risk, or analysis layers.

**Counter-consideration.** Don't over-abstract before the second engine is real. Define the interface from the *two* engines you already have (CEB + legacy) so it is grounded in reality, not speculation. If the legacy solver's signature can't fit the interface cleanly, that is a useful signal — design the interface around CEB and adapt legacy to it.

---

## Recommendation 3 — Quarantine the scaffolding

**Problem.** `debug_*`, `verify_*`, `regenerate_*`, `populate_*`, `create_*`, and the ad-hoc `test_*` scripts sit beside real modules.

**Recommendation.**
- Move all one-offs to an explicit `archive/scaffolding/` (out of the import path). They are historical record, not pipeline code.
- Replace the four ad-hoc `test_*` scripts with a real `tests/` suite (`pytest`), porting their *assertions*. The historical bugs they caught (hour-indexing, sensor-count mismatch, scenario seed collapse) are exactly the regression tests worth keeping.

**Counter-consideration.** The `verify_*` scripts encode hard-won validation logic (material changes actually propagated, hour indexing aligned). Don't just delete — mine them for test cases first. They are the cheapest source of a regression suite you'll ever get.

---

## Recommendation 4 — Finish the config migration

**Problem.** `config.yaml` + `config_locator` enforce "no hardcoded defaults," but the orchestration scripts bypass it with absolute paths and inline constants.

**Recommendation.** In v1 (`treeheat/config.py`), make the config loader the **only** path/parameter source, and add a `validate_config()` startup check that fails loudly on missing keys or non-existent paths. Use relative paths resolved against the config-file directory (the archive already does this for the model dirs — extend it everywhere). This is what makes the pipeline portable across machines and agents.

**Counter-consideration.** A strict "fail on missing key" policy can be painful during exploration. Provide a documented `defaults.yaml` layer that `config.yaml` overrides, so there *is* one explicit place defaults live — not scattered through code, but not absent either.

---

## Recommendation 5 — Separate the data-retention decision from the code cleanup

**Problem.** ~1.2 GB of the 1.4 GB repo is simulation output, not code: `raytracing_results/` (500 MB), `analysis_outputs/` (274 MB), `outputs/` (163 MB), `archive/` (137 MB), `debug_raytracing_results/` (134 MB).

**Recommendation.** This is a **research-data decision, not an engineering one — it is yours to make, not the agents'.** Options, in rough order of preference:

1. **Keep one canonical result set** (the 25-scenario run behind the paper) as a reproducibility anchor; delete the `debug_*` output dirs outright.
2. **Move large outputs out of git** entirely — DVC, git-LFS, or an external data store — and keep only a manifest in the repo.
3. **Regenerate-on-demand:** keep inputs + code, discard derived outputs, document the command to rebuild them.

Whatever you choose, v1 treats `outputs/` as **generated and git-ignored**, never committed (implemented in `treeheat/.gitignore`).

**Counter-consideration.** The raytracing outputs are expensive to recompute (annual Radiance runs). Deleting them trades disk for compute. If recompute is slow or the original geometry/grids are fragile to reproduce, lean toward option 2 (move out of git but keep) rather than option 3 (discard).

---

## Recommendation 6 — Document the Stage 2→3 seam, or automate it

**Problem.** The fragile, manual handoff is exporting Rhino/Grasshopper geometry + sensor grids into a Radiance project. There is no scripted bridge; it lives in a `.gh` definition (`model_archive/`).

**Recommendation.** At minimum, write a short runbook for the export. Better: investigate scripting it (Honeybee/Ladybug already export to Radiance; a headless or `rhino3dm`/`compute.rhino3d` path may remove the GUI step). This is the highest-value automation target for reaching a true end-to-end pipeline — flag it for the new team but don't assume it's trivial.

**Counter-consideration.** Headless Rhino/Grasshopper automation is notoriously brittle and licensing-bound. Scope this as a research spike, not a guaranteed deliverable.

---

## Recommendation 7 — A researcher-facing workflow interface (build it LAST, as a thin skin)

**Problem.** Driving the pipeline from a terminal or Jupyter is friction for the researchers who will actually run scenario sweeps. A simple interface for *setup → execution → basic analysis* is wanted.

**Recommendation.** Build it — but as a **thin skin over the orchestration core, not a parallel system**, and only after the pipeline runs. Full design in [`05_workflow_interface.md`](05_workflow_interface.md). The essentials:

- The UI **cannot escape the backend**. Annual Radiance runs are heavy local compute; a browser can't run them. Setup, execution, and analysis all route through the same Python pipeline. The interface is presentation only.
- This makes an **orchestration core a prerequisite**, not an option: a job spec (a batch of scenarios), a runner that skips already-computed work and writes provenance, and run-state on disk the UI can poll. Most of this already exists informally inside `MaterialScenarioWorkflow` — formalise it.
- Recommended form factor: a **local Streamlit app**, three screens (Setup / Run / Results), localhost only, no auth or deployment. Gradio is the simpler-but-plainer alternative.
- The one real engineering risk is the **job model**: long runs must execute as background processes that survive the UI session, with the UI polling a status file. Design this first.

**Counter-consideration — this is the most likely place to over-build.** A workflow GUI does not help reproduce the paper's numbers; the science port does. Every hour on interface polish is an hour not porting physics. Hold the interface to three screens and the plots that already exist; resist it becoming a BI tool or a scenario IDE. If it can't stay a weekend on top of a working core, it's out of scope.

---

## What NOT to change

- **`METHODOLOGY.md`** — inherit as-is; it is the physics spec.
- **The module layering** (config → IO → radiance → physics → risk → viz). It is already clean; v1 preserves it at `treeheat/`.
- **The databases' schema** (`tree_species_database.csv`, `root_material_database.csv`) — well-designed, citation-backed. Carry forward.
- **`config.yaml` as single source of truth** — the *principle* is right; just enforce it everywhere.

---

## Suggested sequencing for the new team

Phases 1–6 are **complete** (see `.agent/local_memory/INDEX.md`). Remaining:

1. ~~Stand up the skeleton + `config.py` + `validate_config()`.~~ **Done (Phase 1).**
2. ~~Port the **databases and `METHODOLOGY`** (no logic risk).~~ **Done (Phase 2).**
3. ~~Port the **physics modules** behind the engine interface; get CEB passing a single-tree test.~~ **Done (Phase 3).**
4. ~~Port **radiance + risk + analysis**; reproduce the paper's headline numbers as the **acceptance test**.~~ **Done (Phase 4 — gate PASS).**
5. ~~Wire the **CLI** + the **orchestration core**; retire the old scripts.~~ **Done (Phase 5).**
6. ~~Make the **data-retention** call (Rec. 5).~~ **Done (Phase 6).**
7. Tackle the Stage 2→3 automation spike (Rec. 6).
8. *Last:* the researcher-facing **workflow interface** (Rec. 7), as a thin skin over step 5.

Reproducing the paper's numbers (step 4) was the objective definition of "the port worked." The workflow interface (step 8) is deliberately last — it has nothing to drive until the pipeline runs.
