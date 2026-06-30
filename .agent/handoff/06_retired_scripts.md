# Retired v0 orchestration scripts

> **Status:** Decommissioned in Phase 5. Files remain in read-only `src_archive/` for reference.

| v0 script | Replaced by |
|-----------|-------------|
| `src_archive/workflow.py` | `treeheat run raytrace` / `treeheat run all` via [treeheat/orchestration/runner.py](../treeheat/treeheat/orchestration/runner.py) |
| `src_archive/workflow_analysis.py` | `treeheat run biophysics` + `treeheat run analyze` |
| `src_archive/example_usage.py` | `treeheat run all` and [treeheat/api.py](../treeheat/treeheat/api.py) |
| `src_archive/run_analysis.py` | `treeheat run analyze` → [treeheat/risk/analysis.py](../treeheat/treeheat/risk/analysis.py) |
| `src_archive/material_scenario_workflow.py` | [treeheat/pipeline/raytrace.py](../treeheat/treeheat/pipeline/raytrace.py) + orchestration runner |

## 25-scenario sweep

The 5×5 landscape/facade naturalness grid (25 unique pairs at 0.0–1.0 in steps of 0.25) from the paper sweep is preserved as **`simulation.instructions`** in [treeheat/config/defaults.yaml](../treeheat/config/defaults.yaml), matching **`src_archive/config.yaml`** scenario order (facade outer, landscape inner). Config is the single source of truth — do not regenerate inline in code.

Note: `workflow_analysis.py` used a different loop nesting when generating scenarios ad hoc; the frozen 25-scenario run and acceptance gate follow **config.yaml**, not that script's iteration order.

## Canonical entry points (v1)

```bash
treeheat run raytrace   --config config/config.yaml
treeheat run biophysics --config config/config.yaml
treeheat run analyze    --config config/config.yaml
treeheat run all        --config config/config.yaml
treeheat status         --config config/config.yaml
```

Python API: `from treeheat import run, status, load_analysis`
