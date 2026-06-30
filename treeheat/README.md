# treeheat — v1 clean rebuild

Config-driven tree thermal-safety simulation pipeline. Layering:

```
config -> io -> radiance -> physics(engines) -> risk -> viz
```

Phases 1–6 complete. Acceptance gate passed (albedo +61.04 %/unit R²=0.871;
emissivity −194.21 %/unit). CLI + orchestration core (JobSpec, content-addressed
Runner, provenance, `treeheat status`) operational.

## Quick start

From this directory (`thermal-sandbox/treeheat/`):

```bash
uv sync --extra dev              # base deps + pytest/ruff; creates .venv
uv run pytest                    # 39 tests (36 fast + 3 slow acceptance)
uv run treeheat --help           # CLI entry point
uv run treeheat status           # inspect run state
```

Full pipeline (requires Radiance on PATH for raytracing):

```bash
uv sync --extra physics --extra radiance --extra geo --extra viz --extra dev
uv run treeheat run all --config config/config.yaml
```

Commit `uv.lock` for reproducible installs across agents. `.venv/` is git-ignored.

## Environment setup (uv)

Optional extras (add when needed):

```bash
uv sync --extra physics --extra dev   # scipy solvers
uv sync --extra radiance --extra geo --extra viz --extra dev   # full pipeline
uv sync --extra ui --extra dev        # Phase 8 — Streamlit UI
```

## System-level prerequisites (NOT pip deps)

These are documented separately and are not captured in `uv.lock`:

- **Radiance** — `pyradiance` wraps Radiance; the Radiance binaries must be on `PATH`
  when running raytracing.
- **Geo stack** — `geopandas` wheels usually bundle GDAL/GEOS/PROJ. If `uv sync --extra geo`
  fails on your Mac, install the geo stack via conda/mamba for that extra.

## Config

Two layers:

- **Package defaults** — `treeheat/defaults.yaml` (shipped with the package; single source of truth).
- **Project `config/config.yaml`** — paths (relative to the config dir) and run overrides.

External projects use `treeheat init <dir>`; they need only `config/config.yaml` (no local `defaults.yaml`).

```python
from treeheat.config import get_config, get_path, validate_config

cfg = get_config("config/config.yaml")
validate_config(cfg)
weather = get_path("weather_file", cfg)
```

`validate_config()` fails loudly on missing keys or missing input paths. Output directories
are created if absent.

## External projects

```bash
treeheat init ~/Projects/my_site          # scaffold external project
treeheat validate --config config/config.yaml
treeheat run all --config config/config.yaml
```

See `docs/runbook_gh_to_project.md` for the Grasshopper → Radiance export procedure.

## UI (Phase 8)

```bash
uv sync --extra ui --extra viz --extra dev
uv run streamlit run app/streamlit_app.py
```

Streamlit is an **optional extra** (`ui`); a plain `uv sync` does not install it. Use
`uv run streamlit …` (or `source .venv/bin/activate` first) — the binary is not on your
global shell PATH.

Four views: **Setup** (project + overrides), **Guide** (runbook), **Run** (background launch + status), **Results** (plots + table).

## Package layout

```
treeheat/                  <- project dir (this directory)
  treeheat/                <- importable package
    orchestration/         job spec, runner, provenance (Phase 5)
    pipeline/              biophysics + raytrace drivers (Phase 4)
  config/                  defaults.yaml + config.yaml
  data/                    species + material databases (Phase 2)
  outputs/                 generated, git-ignored
  tests/
  pyproject.toml, uv.lock
```

Full rationale: `../.agent/handoff/03_consolidation_recommendations.md`.
Phase history: `../.agent/local_memory/INDEX.md`.
