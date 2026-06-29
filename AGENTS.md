# AGENTS.md — Read this first

This repository status is **v0**: archive and reference material only. It is not the working tree.

A new pipeline (**v1**) is being built *from* this material by an agent team. If you are
that agent (or onboarding one), your orientation set lives here:

## → Start at [`.agent/handoff/README.md`](.agent/handoff/README.md)

That folder contains the project description, a guide to the v0 code, consolidation
recommendations, a token-cheap archive map, and a placeholder skeleton for v1.

## Ground rules

- **`src_archive/`, `model_archive/`, `analysis_archive/` are READ-ONLY reference (v0).** Do not edit or extend them in place. Build v1 in a clean tree per the handoff.
- **Do not load archive directories wholesale.** They total ~1.5 GB, mostly simulation data. Use `.agent/handoff/04_archive_map.md` to open only the one file you need.
- **`.agent/handoff/` is the source of truth for intent.** `.agent/local_memory/` is agent working state, not project source.
