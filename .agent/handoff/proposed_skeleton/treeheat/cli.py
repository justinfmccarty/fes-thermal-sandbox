"""Single entry point — replaces the 5 overlapping archive scripts.

Replaces: run_analysis.py, material_scenario_workflow.py (as script), workflow.py,
          workflow_analysis.py, example_usage.py.

Usage:
    treeheat run raytrace   --config config/config.yaml   # Stage 3
    treeheat run biophysics --config config/config.yaml   # Stage 4
    treeheat run analyze    --config config/config.yaml   # Stage 5
    treeheat run all        --config config/config.yaml

Design: the CLI is for REPRODUCIBLE runs. Notebooks import the same functions
directly for EXPLORATION. All parameters come from config — no CLI flags for science.
"""
from __future__ import annotations
import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="treeheat")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run a pipeline stage")
    run.add_argument("stage", choices=["raytrace", "biophysics", "analyze", "all"])
    run.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args(argv)
    raise NotImplementedError(f"Wire stage={args.stage!r} to the pipeline modules.")


if __name__ == "__main__":
    raise SystemExit(main())
