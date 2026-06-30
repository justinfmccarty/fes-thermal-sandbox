# AGENTS.md — Read this first

This repository holds **v0 archives** (read-only reference) and the **v1 working pipeline**
at top-level `treeheat/` (Phases 1–6 complete; acceptance gate passed). If you are an
agent (or onboarding one), your orientation set lives here:

## → Start at [`.agent/handoff/README.md`](.agent/handoff/README.md)

That folder contains the project description, a guide to the v0 code, consolidation
recommendations, a token-cheap archive map, and pointers to the built v1 package at
`treeheat/`.

## Ground rules

- **`src_archive/`, `model_archive/`, `analysis_archive/` are READ-ONLY reference (v0).** Do not edit or extend them in place. Build v1 in a clean tree per the handoff.
- **Do not load archive directories wholesale.** They total ~1.5 GB, mostly simulation data. Use `.agent/handoff/04_archive_map.md` to open only the one file you need.
- **`.agent/handoff/` is the source of truth for intent.** `.agent/local_memory/` is agent working state, not project source.
