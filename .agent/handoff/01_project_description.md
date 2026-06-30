# Project Description — Thermal Safety of Trees vs. Landscape Surface Type

> **Audience:** The agent team building v1 from this v0 archive (and any human lead reviewing their work).
> **Status:** Handoff document. Describes the *intended* research pipeline and where the current archive sits within it.
> **Companion docs:** [`02_codebase_guide.md`](02_codebase_guide.md) · [`03_consolidation_recommendations.md`](03_consolidation_recommendations.md) · [`04_archive_map.md`](04_archive_map.md)

---

## 1. The research question

Urban trees are increasingly relied on for cooling, yet the trees themselves can be heat-stressed by the surfaces around them. Hard, low-albedo, high-emissivity landscape and façade materials re-radiate shortwave and longwave energy onto nearby canopies, raising leaf temperature toward physiologically critical thresholds.

**Core question:** *How does the choice of landscape surface and building façade material change the thermal heat-stress load on adjacent trees?*

The project answers this by simulating, hour-by-hour, the leaf temperature and physiological stress of individual trees under different material scenarios, then ranking which material choices most reduce (or worsen) tree heat stress.

The first attempt at this question is the conference paper in [`analysis_archive/conference_paper.pdf`](../../analysis_archive/conference_paper.pdf). The codebase in `src_archive/` is the simulation machinery built for that paper.

---

## 2. The intended pipeline (five stages)

The full vision runs from raw aerial capture to a per-tree stress ranking. **Not all five stages exist as code in this repository** — that is flagged explicitly below, because it is the single most important thing for a new team to understand before they plan their work.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 1   Aerial capture                                                 │
│  Photogrammetry + LiDAR + infrared (thermal) channel                      │
│  → point clouds, orthomosaics, surface temperature imagery                │
│  CODE IN REPO: none. External capture/processing. Raw data not stored here.│
├─────────────────────────────────────────────────────────────────────────┤
│  STAGE 2   3D model building                                              │
│  Rhino + Grasshopper (Honeybee/Ladybug), sky-view factor pre-compute       │
│  → watertight scene geometry, material-tagged surfaces, sensor grids       │
│  CODE IN REPO: model_archive/ (.3dm, .gh, .hbjson, svf/). Reference only.   │
├─────────────────────────────────────────────────────────────────────────┤
│  STAGE 3   Raytracing                                                     │
│  Radiance, 2-phase daylight-coefficient (DDS) annual irradiance            │
│  → per-sensor direct + diffuse shortwave irradiance (feather files)        │
│  CODE IN REPO: src_archive/radiance.py + python/*_radiance_project/. Active.│
├─────────────────────────────────────────────────────────────────────────┤
│  STAGE 4   Biophysical heat-stress modelling                             │
│  Coupled ground ↔ leaf ↔ soil-moisture energy balance (Li 2023 CEB)        │
│  → hourly leaf temperature, transpiration, surface/MRT per tree            │
│  CODE IN REPO: src_archive/ physics modules. Active. This is the core.      │
├─────────────────────────────────────────────────────────────────────────┤
│  STAGE 5   Risk metrics & scenario analysis                              │
│  Degree-hours, critical-threshold exceedance, material sensitivity         │
│  → ranked material scenarios, sensitivity slopes, report + plots           │
│  CODE IN REPO: src_archive/ risk + analysis modules. Active.                │
└─────────────────────────────────────────────────────────────────────────┘
```

### Where the seams are (gap flags)

| Stage | Code present? | Lives in | What a new team must know |
|------|----------------|----------|----------------------------|
| 1 — Photogrammetry / LiDAR / IR | **No** | — | The front end is upstream and undocumented in code. Inputs arrive as already-processed geometry and sensor points. If end-to-end automation is a goal, this stage must be **built from scratch**. |
| 2 — Rhino / Grasshopper | Partial (artifacts only) | `model_archive/DLA Study Model/` | The `.gh` definition and `.3dm` model exist, but they are GUI/visual-programming artifacts, not scripted/repeatable code. Re-running requires Rhino + the same plugins. |
| 3 — Radiance | **Yes** | `src_archive/radiance.py` | Scripted and runnable via `pyradiance`. The handoff between Stage 2 and 3 (exporting geometry + grids into a Radiance project) is the most fragile, manual seam. |
| 4 — Biophysics | **Yes** | `src_archive/` | Well-structured, config-driven. The scientific heart of the project. |
| 5 — Risk / analysis | **Yes** | `src_archive/` | Runnable; produces the report and plots behind the paper. |

**Practical takeaway:** what exists as maintainable, scriptable code is essentially the **back half** of the pipeline (Stages 3–5). Stages 1–2 are a data-and-tooling boundary the new team inherits, not a codebase they can simply extend.

---

## 3. The science, briefly

The model is a **coupled ground–leaf–soil biophysical system** evaluated hourly. Material properties (albedo α, emissivity ε) drive the surface energy balance, which sets ground temperature, which feeds the canopy energy balance, which yields leaf temperature and stress. Soil-moisture dynamics close a feedback loop onto stomatal resistance.

The three radiative/thermal couplings:

1. **Shortwave.** Downwelling shortwave from Radiance (`K_down = direct + diffuse`) is partly absorbed by the ground (`1−α`) and partly reflected upward (`α·K_down`) onto the canopy.
2. **Longwave.** The ground emits `ε·σ·Tg⁴` upward to the leaf; the sky contributes `ε_atm·σ·Ta⁴` weighted by sky-view factor.
3. **Canopy energy balance.** Incoming shortwave + longwave, minus leaf emission and latent/sensible exchange, solved for steady-state leaf temperature `Tf`.

The current canopy engine is the **Li et al. (2023) tree-scale canopy energy balance (CEB)** model (*Sustainable Cities and Society* 99:104994). It is the project's **current drop-in engine, not a permanent commitment** — the architecture should treat the canopy model as swappable (see [`03_consolidation_recommendations.md`](03_consolidation_recommendations.md)).

Full equations, constants, and references are documented in [`src_archive/METHODOLOGY.md`](../../src_archive/METHODOLOGY.md) — that file is authoritative for the physics and should be inherited, not rewritten.

---

## 4. The experiment that was run

The first study (the conference paper) simulated a real site in **Winnipeg, Manitoba** ("DLA Study" / "jodla" project):

- **Trees:** ~147 individual trees with species-specific physiology.
- **Species:** 34-row species database (e.g. White Spruce *Picea glauca*) with leaf optical, stomatal, and thermal-threshold parameters.
- **Materials:** 16-row material database, each scored 0–1 for "naturalness" (1.0 = tall grass; low = hard/reflective).
- **Scenarios:** 25 material scenarios sweeping landscape and façade naturalness on a 0–100% grid (5×5).
- **Weather:** Winnipeg TMY (EPW). Baseline = full annual (8,760 h); scenarios = warmest week (168 h) for speed.
- **Headline result:** Risk is highly sensitive to material albedo (slope ≈ 61%/unit, R²≈0.87) and emissivity (slope ≈ −194%/unit, R²≈0.64). Best case (100% natural landscape) reduced risk ~5% vs. the 50/50 reference; worst case (100% hard façade) raised it ~13%.

This establishes that **material choice measurably moves tree heat stress** — the result the new, tighter pipeline is meant to reproduce more efficiently and at larger scale.

---

## 5. What "handing off" means here

The existing `src_archive/` is a **research codebase**: it works and produced a paper, but it accreted scaffolding, competing entry points, and hardcoded paths along the way. The new team is **not** inheriting it directly. They are inheriting:

1. The **science** (`METHODOLOGY.md`, the databases, the validated result).
2. A **map** to the working code so they can port what is proven ([`04_archive_map.md`](04_archive_map.md)).
3. The **v1 pipeline** at top-level [`treeheat/`](../../treeheat/) — built from the retired scaffold in Phases 1–6. Pluggable canopy engine, config-driven CLI, orchestration core, acceptance gate passed.

The goal was a tighter, more automatable pipeline — not a port of the old one. Phases 1–6 delivered that; Phases 7–8 remain.
