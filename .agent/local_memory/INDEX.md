# Local Memory — Index

Chronological pointers to agent memory records. Newest at the bottom.

- [20260629-1535] Phase 0 — roadmap: objective + acceptance gate restated; 8-phase build order with deps/done; top-3 gate risks; decisions — gate uses frozen v0 feathers, v1 lives at top-level `treeheat/`. See `20260629-1535_phase00_roadmap.md`.
- [20260629-1600] Phase 1 — skeleton + config: v1 package at `treeheat/`; config loader (defaults+run merge, validate_config, get_path); lazy engine registry; light pyproject + uv.lock; 11 tests pass. See `20260629-1600_phase01_skeleton-config.md`.
- [20260629-1705] Phase 2 — reference data: species + material CSVs in `treeheat/data/`; typed loaders with schema validation; methodology pointer doc; 22 tests pass. See `20260629-1705_phase02_reference-data.md`.
- [20260629-1815] Phase 3 — physics + engines: CanopyEngine interface from CEB+legacy; ground/surface/soil/upwelling ports; integrator via get_engine(); v0 differential CEB test passes; 25 tests pass. See `20260629-1815_phase03_physics-engines.md`.
- [20260630-0635] Phase 4 — back-half pipeline + acceptance gate: weather, risk metrics, scenario driver, cross-scenario analysis, plots, radiance runner (lazy pyradiance), CLI; two-tier acceptance test PASS (albedo +61.04 R²=0.871, emissivity -194.21, best S004 -5.21%, worst S020 +12.76%). See `20260630-0635_phase04_pipeline-acceptance.md`.
- [20260630-0700] Phase 5 — CLI + orchestration core: JobSpec, content-addressed Runner (skip/adopt), provenance sidecars, run_state.json, `treeheat status`, thin `treeheat.api`; v0 scripts decommissioned via handoff map; 39 tests pass (36 fast + 3 slow). See `20260630-0700_phase05_cli-orchestration.md`.
- [20260630-0720] Phase 6 — data retention (Rec. 5): v0 heavy outputs stay gitignored + off-machine backup; deleted debug/archive throwaway (~275 MB); committed headline CSVs; forward principle = external project dirs, outputs never in repo. See `20260630-0720_phase06_data-retention.md`.
