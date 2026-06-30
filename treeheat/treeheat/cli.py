"""Single config-driven entry point — replaces the five overlapping archive scripts.

Usage:
    treeheat init <dir>
    treeheat validate --config config/config.yaml
    treeheat run raytrace   --config config/config.yaml
    treeheat run biophysics --config config/config.yaml
    treeheat run analyze    --config config/config.yaml
    treeheat run all        --config config/config.yaml
    treeheat status         --config config/config.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from treeheat.config import get_config, reload_config, validate_config
from treeheat.orchestration.runner import Runner
from treeheat.project import init_project, project_config_path, validate_project

STAGE_MAP = {
    "raytrace": ["raytrace"],
    "biophysics": ["biophysics"],
    "analyze": ["analyze"],
    "all": ["raytrace", "biophysics", "analyze"],
}


def _resolve_config_path(config_arg: str) -> Path:
    path = Path(config_arg)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _parse_scenarios(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    ids = [s.strip() for s in raw.split(",") if s.strip()]
    normalized = []
    for sid in ids:
        if sid.startswith("scenario_"):
            normalized.append(sid)
        elif sid.startswith("s") and sid[1:].isdigit():
            normalized.append(f"scenario_{int(sid[1:]):03d}")
        else:
            normalized.append(sid)
    return normalized


def cmd_run(args: argparse.Namespace) -> int:
    config_path = _resolve_config_path(args.config)
    reload_config(config_path)
    cfg = get_config(config_path)
    validate_config(cfg)

    stages = STAGE_MAP[args.stage]
    scenario_ids = _parse_scenarios(args.scenarios)
    runner = Runner(cfg=cfg, config_path=config_path)
    report = runner.run(stages, scenario_ids=scenario_ids, force=args.force)

    print(f"Completed: {len(report.completed)}  Skipped: {len(report.skipped)}  "
          f"Adopted: {len(report.adopted)}  Failed: {len(report.failed)}")
    if report.skipped:
        print(f"  Skipped tasks: {', '.join(report.skipped[:5])}"
              f"{'...' if len(report.skipped) > 5 else ''}")
    if report.adopted:
        print(f"  Adopted existing outputs: {', '.join(report.adopted[:5])}"
              f"{'...' if len(report.adopted) > 5 else ''}")
    if report.failed:
        print(f"  Failed: {', '.join(report.failed)}", file=sys.stderr)
        return 1
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config_path = _resolve_config_path(args.config)
    reload_config(config_path)
    cfg = get_config(config_path)
    runner = Runner(cfg=cfg, config_path=config_path)
    if runner.run_state_path.exists():
        data = json.loads(runner.run_state_path.read_text(encoding="utf-8"))
    else:
        data = runner.load_run_state().to_dict()
    print(json.dumps(data, indent=2))
    return 0


def cmd_materials(args: argparse.Namespace) -> int:
    config_path = _resolve_config_path(args.config)
    reload_config(config_path)
    cfg = get_config(config_path)
    from treeheat.pipeline.grid_materials import write_scenario_grid_materials

    try:
        out = write_scenario_grid_materials(cfg)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    import pandas as pd

    df = pd.read_csv(out)
    scenario_ids = df.loc[df["scenario_id"].astype(str) != "baseline", "scenario_id"]
    print(f"Wrote {out}")
    print(f"  Rows: {len(df)}  Scenarios: {scenario_ids.nunique()}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    try:
        report = init_project(
            args.dir,
            force=args.force,
            with_sample_data=not args.no_sample_data,
        )
    except FileExistsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Initialized project at {report.project_dir}")
    print(f"  Created: {len(report.created_paths)} paths")
    if report.skipped_paths:
        print(f"  Skipped (already present): {len(report.skipped_paths)}")
    print(f"  Config: {project_config_path(report.project_dir)}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    config_path = _resolve_config_path(args.config)
    project_dir = config_path.parent.parent
    report = validate_project(project_dir, check_config=True)
    for item in report.items:
        mark = {"ok": "✓", "missing": "✗", "warning": "~"}[item.status]
        line = f"  [{mark}] {item.path}"
        if item.detail:
            line += f" — {item.detail}"
        print(line)
    if report.config_valid is True:
        print("  [✓] config validation passed")
    elif report.config_valid is False:
        print(f"  [✗] config validation failed: {report.config_error}", file=sys.stderr)
    ready = report.ready
    print(f"\nProject ready: {'yes' if ready else 'no'} ({report.missing_count} missing inputs)")
    return 0 if ready else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="treeheat")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="scaffold an external project directory")
    init_parser.add_argument("dir", help="target project directory")
    init_parser.add_argument(
        "--force", action="store_true", help="scaffold even if directory is not empty"
    )
    init_parser.add_argument(
        "--no-sample-data",
        action="store_true",
        help="create layout only; do not copy starter databases",
    )
    init_parser.set_defaults(func=cmd_init)

    validate_parser = sub.add_parser("validate", help="check project layout and config")
    validate_parser.add_argument("--config", default="config/config.yaml")
    validate_parser.set_defaults(func=cmd_validate)

    run_parser = sub.add_parser("run", help="run a pipeline stage")
    run_parser.add_argument(
        "stage", choices=["raytrace", "biophysics", "analyze", "all"]
    )
    run_parser.add_argument("--config", default="config/config.yaml")
    run_parser.add_argument(
        "--force", action="store_true", help="re-run even if outputs are up to date"
    )
    run_parser.add_argument(
        "--scenarios",
        default=None,
        help="comma-separated scenario ids (e.g. scenario_000,s012)",
    )
    run_parser.set_defaults(func=cmd_run)

    status_parser = sub.add_parser("status", help="print machine-readable run-state JSON")
    status_parser.add_argument("--config", default="config/config.yaml")
    status_parser.set_defaults(func=cmd_status)

    materials_parser = sub.add_parser(
        "materials",
        help="generate scenario_grid_materials.csv from baseline + config instructions",
    )
    materials_parser.add_argument("--config", default="config/config.yaml")
    materials_parser.set_defaults(func=cmd_materials)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Pipeline error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
