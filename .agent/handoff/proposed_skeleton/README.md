# treeheat — proposed skeleton (placeholders only)

A clean, optimized starting structure for the **new agent team** rebuilding the tree
thermal-safety pipeline. **Nothing here is implemented** — every module is a stub that
names the archive file to port *from* and the design contract to honour.

This is a proposal, not a mandate. Stress-test it before committing.

## Why this shape

It preserves the one genuinely good thing about the archive — a clean, layered
dependency graph — while fixing the three things that made it hard to inherit:
one entry point instead of five, a pluggable canopy engine instead of two tangled
models, and config as the enforced single source of truth.

```
treeheat/
  config.py            single source of truth + validate_config()
  cli.py               ONE entry point (raytrace | biophysics | analyze | all)
  io/                  weather, species, materials, grids
  radiance/            DDS 2-phase runner, upwelling
  physics/
    integrator.py      couples everything; depends only on the engine INTERFACE
    ground / surface / soil_moisture
    engines/
      base.py          CanopyEngine ABC  ← the swap contract
      li2023_ceb.py    current default
      legacy_leaf.py   prior engine (cross-check)
  risk/                metrics, cross-scenario analysis
  viz/                 plots
config/                defaults.yaml  +  config.yaml (paths, relative & portable)
data/                  inputs (databases, weather, grids)
outputs/               GENERATED, git-ignored
tests/                 engine tests + the acceptance gate
```

## The two design decisions to understand first

**1. Swap the canopy model in one line.** The integrator never imports a concrete
model — it calls `engines.get_engine(config['model']['canopy_engine'])`. Adding an
engine = one new file in `engines/` + one config line. Li 2023 is today's default;
this is deliberately not a commitment.

**2. The acceptance gate defines "done."** `tests/test_acceptance.py` reproduces the
paper's sensitivity numbers (albedo ≈ +61 %/unit R²≈0.87; emissivity ≈ −194 %/unit).
Port until that passes; only then build new science.

## Suggested build order

1. `config.py` + `validate_config()` → fail loudly on bad config.
2. Copy databases + `METHODOLOGY.md` into `data/` (no logic risk).
3. Port `physics/` behind the engine interface; get `li2023_ceb` passing a single-tree test.
4. Port `radiance/` + `risk/`; make the acceptance gate pass.
5. Wire `cli.py`; retire the archive scripts.

Full rationale: `../03_consolidation_recommendations.md`. Where everything lives in
the old tree: `../04_archive_map.md`.
