# Bugfix — material-name substring collision in `_ensure_materials`

**Date:** 2026-06-30 14:50
**Scope:** follow-up to Phase 8 (surfaced by the capstone external project "kings-road")

## Symptom

Running a scenario raytrace on a real external project failed at octree build:

```
oconv: fatal - (.../scenario_000/model/scene/envelope.rad): undefined modifier "glass"
```

Both the baseline and scenario Radiance projects were internally consistent — neither
used a literal `glass` modifier and both defined every modifier they used. The `glass`
modifier only appeared *after* the pipeline's material-swap step.

## Root cause

`RadianceProjectManager.apply_material_scenario` rewrites facade/landscape surfaces to the
chosen scenario materials, then calls `_ensure_materials` to append any missing Radiance
material definitions to the working-copy `envelope.mat`.

The material database for this project contains a material **literally named `glass`**
(`facade_applicable=True`, naturalness 0.1 — the least-natural facade option), so the
scenario rewrite legitimately assigns `glass` as the facade modifier. Its definition
(`void glass glass ...`) exists in `base_material_library.txt`.

`_ensure_materials` decided whether a definition was already present with a naive
substring test:

```python
if mat_def and name not in content:   # BUG
```

Because the file already contained `void glass conifer` / `void glass deciduous` (where
`glass` is the *type*, not the identifier), the substring `"glass"` was found, so the real
`void glass glass` identifier definition was **never appended** → undefined modifier.

## Fix

`treeheat/treeheat/pipeline/raytrace.py`: replaced the substring check with a parse of the
material file's actually-declared identifiers. Added `_defined_material_names(content)`,
which collects the 3rd token (the identifier) of each `modifier type identifier` header
line, and checks membership against that set instead of raw substring containment.

```python
defined = self._defined_material_names(content)
...
if mat_def and name not in defined:
    to_add.append(mat_def)
```

## Verification

- Repro on the real file: old check reported `glass` as "defined" (True); new check
  correctly reports it missing (False), so `void glass glass` is now appended.
- `pytest tests/ -k "not capstone and not acceptance"` → 41 passed.
- Full suite incl. capstone end-to-end (real Radiance run) → 47 passed.

## Notes / deviations

- No change to plan/contract; this is a correctness fix in the existing material-append
  path. The substring heuristic was always fragile for any material whose name is also a
  Radiance type keyword (`glass`, `metal`, `plastic`, `mirror`, `trans`, etc.); the
  identifier-parse approach removes that class of collision generally.
