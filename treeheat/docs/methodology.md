# Physics methodology — authoritative reference

The physics specification for the tree thermal-safety pipeline is **not duplicated here**.
The authoritative document is:

**[`src_archive/METHODOLOGY.md`](../../src_archive/METHODOLOGY.md)** (v0 archive, read-only)

Inherit that spec when implementing or reviewing v1 code. Do not rewrite or copy its content
into this tree.

## Section map (v1 implementation targets)

| METHODOLOGY section | v1 module(s) |
|---------------------|--------------|
| §2 Spatial framework | `io/grids.py`, `radiance/upwelling.py` |
| §3 Radiance irradiance | `radiance/runner.py`, `radiance/upwelling.py` |
| §4 Surface energy balance | `physics/ground.py`, `physics/surface.py` |
| §5 Leaf energy balance (CEB) | `physics/engines/li2023_ceb.py`, `physics/integrator.py` |
| §6 Soil moisture | `physics/soil_moisture.py` |
| §7 Risk metrics | `risk/metrics.py`, `risk/analysis.py` |
| §8 Species parameters | `io/species.py` + `data/tree_species_database.csv` |
| §10 Physical constants | `config/defaults.yaml` |

Material optical/thermal properties come from `data/root_material_database.csv` via
`io/materials.py`. Ground heat capacity, evaporation, and drainage resolve from
`config.model.ground.types[ground_type]` — the CSV placeholder columns
(`heat_capacity_J_m2_K`, `evap_factor`, `k_drain`) are intentionally blank.
