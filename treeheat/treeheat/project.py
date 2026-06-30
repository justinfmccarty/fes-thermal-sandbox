"""External project layout contract and scaffolding.

Projects live OUTSIDE the treeheat package. ``treeheat init <dir>`` creates the
expected directory tree; ``validate_project`` checks readiness before a run.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Literal

import yaml

from treeheat.config import ConfigError, get_config, reload_config, validate_config

__all__ = [
    "PROJECT_LAYOUT",
    "RUNBOOK_FILENAME",
    "InitReport",
    "ProjectValidationReport",
    "ValidationItem",
    "init_project",
    "packaged_runbook_path",
    "project_config_path",
    "project_runbook_path",
    "read_runbook",
    "validate_project",
    "write_config_overrides",
]

CheckStatus = Literal["ok", "missing", "warning"]

RUNBOOK_FILENAME = "runbook_gh_to_project.md"

# Layout paths that are reference-only — absence is a warning, not a blocker.
OPTIONAL_INPUTS: frozenset[str] = frozenset(
    {"inputs/grid_records/baseline_sensor_grid.csv"}
)

# Canonical external-project contract (paths relative to project root unless noted).
PROJECT_LAYOUT: dict[str, str] = {
    "config/config.yaml": "Run config stub (paths + overrides; defaults from package)",
    RUNBOOK_FILENAME: "Grasshopper → Radiance export guide (local copy)",
    "models/": "Rhino (.3dm) and Grasshopper (.gh) source files (reference only)",
    "inputs/weather.epw": "TMY weather file (EPW)",
    "inputs/tree_species_database.csv": "Species physiology database",
    "inputs/root_material_database.csv": "Material optical/thermal database",
    "inputs/base_material_library.txt": "Radiance material definitions (next to material DB)",
    "inputs/grid_records/baseline_trees.csv": "Tree point locations + species",
    "inputs/grid_records/scenario_sensor_grid.csv": "Scenario sensor grid (matches per-scenario raytrace feathers)",
    "inputs/grid_records/baseline_sensor_grid.csv": "Baseline sensor grid (annual-run reference; optional)",
    "inputs/grid_records/baseline_materials.csv": "Baseline grid→material mapping",
    "inputs/grid_records/scenario_grid_materials.csv": "Per-scenario grid material assignments",
    "inputs/radiance/baseline_radiance_project/model/scene/envelope.rad": "Baseline Radiance geometry",
    "inputs/radiance/baseline_radiance_project/model/scene/envelope.mat": "Baseline Radiance materials",
    "inputs/radiance/scenario_radiance_project/model/scene/envelope.rad": "Scenario Radiance geometry",
    "inputs/radiance/scenario_radiance_project/model/scene/envelope.mat": "Scenario Radiance materials",
    "outputs/raytracing/": "Per-scenario direct/diffuse feather files (generated)",
    "outputs/biophysical/": "Per-scenario biophysical CSVs (generated)",
    "outputs/analysis/": "Cross-scenario analysis CSVs + plots (generated)",
    "outputs/provenance/": "Provenance sidecars (generated)",
    "outputs/run_state.json": "Orchestration run-state (generated at first run)",
}

_CONFIG_STUB = """\
# treeheat project config — paths relative to this file.
# Defaults (model params, simulation grid, physical constants) load from the
# treeheat package unless you add matching keys here.

paths:
  weather_file: ../inputs/weather.epw
  species_database_file: ../inputs/tree_species_database.csv
  material_database_file: ../inputs/root_material_database.csv
  grid_records_dir: ../inputs/grid_records
  tree_points_file: ../inputs/grid_records/baseline_trees.csv
  # Used by biophysics; must match the per-scenario raytrace feather columns.
  sensor_points_file: ../inputs/grid_records/scenario_sensor_grid.csv
  # Reference only (annual baseline run); not read by the per-scenario pipeline.
  baseline_sensor_points_file: ../inputs/grid_records/baseline_sensor_grid.csv
  grid_material_mapping_file: ../inputs/grid_records/baseline_materials.csv
  scenario_grid_materials_file: ../inputs/grid_records/scenario_grid_materials.csv
  baseline_project_dir: ../inputs/radiance/baseline_radiance_project
  scenario_project_dir: ../inputs/radiance/scenario_radiance_project
  raytracing_results_dir: ../outputs/raytracing
  biophysical_outputs_dir: ../outputs/biophysical
  analysis_results_dir: ../outputs/analysis

# --- Run overrides (edit here or via the UI Setup screen) ---
model:
  canopy_engine: li2023_ceb

analysis:
  period_type: warmest_week
"""

_GITIGNORE = """\
# treeheat generated outputs — never commit
outputs/
*.pyc
__pycache__/
.DS_Store
"""

_README = """\
# treeheat project

External simulation project for the treeheat pipeline.

## Next steps

1. Place your Rhino/Grasshopper files in `models/` (reference; not read by the pipeline).
2. Follow `runbook_gh_to_project.md` (in this project folder) to export
   geometry and grids from Rhino/Grasshopper into `inputs/`.
3. Place your weather file at `inputs/weather.epw`.
4. Validate: `treeheat validate --config config/config.yaml`
5. Run: `treeheat run all --config config/config.yaml`
6. Or launch the UI: `uv run streamlit run <path-to-treeheat>/app/streamlit_app.py`

Outputs land in `outputs/` (git-ignored).
"""


@dataclass
class ValidationItem:
    path: str
    description: str
    status: CheckStatus
    detail: str = ""


@dataclass
class ProjectValidationReport:
    project_dir: Path
    items: list[ValidationItem] = field(default_factory=list)
    config_valid: bool | None = None
    config_error: str | None = None

    @property
    def ready(self) -> bool:
        if any(i.status == "missing" for i in self.items):
            return False
        return self.config_valid is True

    @property
    def missing_count(self) -> int:
        return sum(1 for i in self.items if i.status == "missing")


@dataclass
class InitReport:
    project_dir: Path
    created_paths: list[str] = field(default_factory=list)
    skipped_paths: list[str] = field(default_factory=list)


def project_config_path(project_dir: Path | str) -> Path:
    return Path(project_dir).resolve() / "config" / "config.yaml"


def project_runbook_path(project_dir: Path | str) -> Path:
    return Path(project_dir).resolve() / RUNBOOK_FILENAME


def packaged_runbook_path() -> Path:
    """Canonical runbook shipped with the treeheat package."""
    pkg_root = Path(resources.files("treeheat"))
    candidate = pkg_root / "project_data" / RUNBOOK_FILENAME
    if candidate.exists():
        return candidate
    dev_docs = Path(__file__).resolve().parent.parent / "docs" / RUNBOOK_FILENAME
    if dev_docs.exists():
        return dev_docs
    raise FileNotFoundError(f"Packaged runbook not found: {RUNBOOK_FILENAME}")


def read_runbook(project_dir: Path | str | None = None) -> str:
    """Return runbook markdown — project-local copy if present, else packaged."""
    if project_dir is not None:
        local = project_runbook_path(project_dir)
        if local.is_file() and local.stat().st_size > 0:
            return local.read_text(encoding="utf-8")
    return packaged_runbook_path().read_text(encoding="utf-8")


def _package_data_path(name: str) -> Path:
    """Resolve a file shipped under treeheat/data/ (dev) or project_data/."""
    pkg_root = Path(resources.files("treeheat"))
    candidate = pkg_root / "project_data" / name
    if candidate.exists():
        return candidate
    # Dev layout: sibling data/ directory next to package
    dev_data = Path(__file__).resolve().parent.parent / "data" / name
    if dev_data.exists():
        return dev_data
    raise FileNotFoundError(f"Packaged starter data not found: {name}")


def _write_if_absent(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _copy_if_absent(src: Path, dest: Path, *, force: bool) -> bool:
    if dest.exists() and not force:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def init_project(
    project_dir: Path | str,
    *,
    force: bool = False,
    with_sample_data: bool = True,
) -> InitReport:
    """Scaffold an external treeheat project directory."""
    root = Path(project_dir).resolve()
    report = InitReport(project_dir=root)
    root.mkdir(parents=True, exist_ok=True)

    if any(root.iterdir()) and not force:
        raise FileExistsError(
            f"Project directory is not empty: {root}\n"
            "Pass force=True to scaffold anyway."
        )

    # Directories (including output dirs the orchestrator expects)
    dir_keys = [k for k in PROJECT_LAYOUT if k.endswith("/")]
    for rel in dir_keys:
        path = root / rel
        if not path.exists() or force:
            path.mkdir(parents=True, exist_ok=True)
            report.created_paths.append(rel)
        else:
            report.skipped_paths.append(rel)

    models_keep = root / "models" / ".gitkeep"
    if _write_if_absent(models_keep, "", force=force):
        report.created_paths.append("models/.gitkeep")

    # Radiance scene placeholders (user replaces via runbook)
    radiance_dirs = [
        "inputs/radiance/baseline_radiance_project/model/scene",
        "inputs/radiance/scenario_radiance_project/model/scene",
        "inputs/radiance/baseline_radiance_project/model/grid",
        "inputs/radiance/scenario_radiance_project/model/grid",
    ]
    for rel in radiance_dirs:
        (root / rel).mkdir(parents=True, exist_ok=True)

    # Config + meta files
    for rel, content in [
        ("config/config.yaml", _CONFIG_STUB),
        (".gitignore", _GITIGNORE),
        ("README.md", _README),
    ]:
        path = root / rel
        if _write_if_absent(path, content, force=force):
            report.created_paths.append(rel)
        else:
            report.skipped_paths.append(rel)

    runbook_dest = root / RUNBOOK_FILENAME
    if _copy_if_absent(packaged_runbook_path(), runbook_dest, force=force):
        report.created_paths.append(RUNBOOK_FILENAME)
    else:
        report.skipped_paths.append(RUNBOOK_FILENAME)

    if with_sample_data:
        for name in ("tree_species_database.csv", "root_material_database.csv"):
            src = _package_data_path(name)
            dest = root / "inputs" / name
            if _copy_if_absent(src, dest, force=force):
                report.created_paths.append(f"inputs/{name}")
            else:
                report.skipped_paths.append(f"inputs/{name}")

        base_lib_src = _package_data_path("base_material_library.txt")
        base_lib_dest = root / "inputs" / "base_material_library.txt"
        if _copy_if_absent(base_lib_src, base_lib_dest, force=force):
            report.created_paths.append("inputs/base_material_library.txt")
        else:
            report.skipped_paths.append("inputs/base_material_library.txt")

        # Placeholder grid/radiance files the runbook replaces
        placeholders = {
            "inputs/weather.epw": "# Replace with your EPW weather file\n",
            "inputs/grid_records/baseline_trees.csv": (
                "tree_id,xcoord,ycoord,zcoord,species,SVF\n"
            ),
            "inputs/grid_records/scenario_sensor_grid.csv": (
                "grid_name,xcoord,ycoord,zcoord\n"
            ),
            "inputs/grid_records/baseline_sensor_grid.csv": (
                "grid_name,xcoord,ycoord,zcoord\n"
            ),
            "inputs/grid_records/baseline_materials.csv": (
                "grid_id,material_name,surface_type\n"
            ),
            "inputs/grid_records/scenario_grid_materials.csv": (
                "scenario_id,grid_id,material_name\n"
            ),
            "inputs/radiance/baseline_radiance_project/model/scene/envelope.rad": (
                "# Replace via runbook — baseline Radiance geometry\n"
            ),
            "inputs/radiance/baseline_radiance_project/model/scene/envelope.mat": (
                "# Replace via runbook — baseline Radiance materials\n"
            ),
            "inputs/radiance/scenario_radiance_project/model/scene/envelope.rad": (
                "# Replace via runbook — scenario Radiance geometry\n"
            ),
            "inputs/radiance/scenario_radiance_project/model/scene/envelope.mat": (
                "# Replace via runbook — scenario Radiance materials\n"
            ),
        }
        for rel, content in placeholders.items():
            path = root / rel
            if _write_if_absent(path, content, force=force):
                report.created_paths.append(rel)
            else:
                report.skipped_paths.append(rel)

    return report


def validate_project(project_dir: Path | str, *, check_config: bool = True) -> ProjectValidationReport:
    """Check that a project directory matches the layout contract."""
    root = Path(project_dir).resolve()
    report = ProjectValidationReport(project_dir=root)

    for rel, description in PROJECT_LAYOUT.items():
        path = root / rel
        if rel.endswith("/"):
            status: CheckStatus = "ok" if path.is_dir() else "missing"
        elif rel == "outputs/run_state.json":
            status = "ok" if path.exists() else "warning"
            detail = "Created on first run" if status == "warning" else ""
            report.items.append(
                ValidationItem(path=rel, description=description, status=status, detail=detail)
            )
            continue
        elif rel == RUNBOOK_FILENAME:
            status = "ok" if path.is_file() and path.stat().st_size > 0 else "warning"
            detail = "Re-run treeheat init --force to restore" if status == "warning" else ""
            report.items.append(
                ValidationItem(path=rel, description=description, status=status, detail=detail)
            )
            continue
        else:
            absent_status: CheckStatus = "warning" if rel in OPTIONAL_INPUTS else "missing"
            status = "ok" if path.is_file() and path.stat().st_size > 0 else absent_status
            detail = ""
            if path.is_file() and path.stat().st_size == 0:
                status = absent_status
                detail = "Empty (optional)" if rel in OPTIONAL_INPUTS else "File exists but is empty"
            elif path.is_file() and path.read_text(encoding="utf-8", errors="replace").startswith("# Replace"):
                status = absent_status
                detail = "Placeholder — complete the runbook export"
            elif status == "warning":
                detail = "Optional reference (annual baseline run)"
        report.items.append(
            ValidationItem(path=rel, description=description, status=status, detail=detail)
        )

    if check_config:
        cfg_path = project_config_path(root)
        if not cfg_path.exists():
            report.config_valid = False
            report.config_error = f"Missing {cfg_path.relative_to(root)}"
        else:
            try:
                reload_config(cfg_path)
                cfg = get_config(cfg_path)
                validate_config(cfg, config_dir=cfg_path.parent)
                report.config_valid = True
            except (ConfigError, ValueError, FileNotFoundError) as exc:
                report.config_valid = False
                report.config_error = str(exc)

    return report


def write_config_overrides(project_dir: Path | str, overrides: dict[str, Any]) -> Path:
    """Merge overrides into config/config.yaml (run layer only)."""
    cfg_path = project_config_path(project_dir)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Project config not found: {cfg_path}")

    current = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    merged = _deep_merge(current, overrides)
    cfg_path.write_text(yaml.safe_dump(merged, sort_keys=False, default_flow_style=False), encoding="utf-8")
    return cfg_path


def read_config_overrides(project_dir: Path | str) -> dict[str, Any]:
    """Load the run-layer config.yaml (without merging defaults)."""
    cfg_path = project_config_path(project_dir)
    if not cfg_path.exists():
        return {}
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
