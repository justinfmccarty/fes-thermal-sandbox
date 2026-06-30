"""Tests for external project scaffolding and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from treeheat.config import packaged_defaults_path, reload_config
from treeheat.project import init_project, project_config_path, validate_project


def test_packaged_defaults_exists() -> None:
    path = packaged_defaults_path()
    assert path.is_file()
    assert "simulation" in path.read_text(encoding="utf-8")


def test_init_project_creates_layout(tmp_path: Path) -> None:
    project = tmp_path / "my_site"
    report = init_project(project)
    assert report.project_dir == project.resolve()
    assert project_config_path(project).exists()
    assert (project / "inputs" / "tree_species_database.csv").exists()
    assert (project / "outputs" / "biophysical").is_dir()
    assert (project / ".gitignore").exists()
    assert (project / "runbook_gh_to_project.md").exists()
    assert (project / "models").is_dir()


def test_validate_project_reports_placeholders(tmp_path: Path) -> None:
    project = tmp_path / "site"
    init_project(project)
    report = validate_project(project, check_config=False)
    missing = [i.path for i in report.items if i.status == "missing"]
    assert "inputs/weather.epw" in missing
    assert report.config_valid is None


def test_init_project_refuses_nonempty_without_force(tmp_path: Path) -> None:
    project = tmp_path / "site"
    project.mkdir()
    (project / "existing.txt").write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError):
        init_project(project)


def test_init_project_force_on_nonempty(tmp_path: Path) -> None:
    project = tmp_path / "site"
    project.mkdir()
    (project / "existing.txt").write_text("x", encoding="utf-8")
    report = init_project(project, force=True)
    assert project_config_path(project).exists()
    assert len(report.created_paths) > 0


def test_get_path_uses_cfg_root_when_global_config_switches(tmp_path: Path) -> None:
    """Held cfg dict resolves paths from its project even if global config reloads."""
    init_project(tmp_path / "ext_a")
    init_project(tmp_path / "ext_b")
    cfg_a_path = project_config_path(tmp_path / "ext_a")
    cfg_b_path = project_config_path(tmp_path / "ext_b")

    reload_config(cfg_a_path)
    from treeheat.config import get_config, get_path

    cfg_a = get_config(cfg_a_path)
    weather_a = get_path("weather_file", cfg_a)

    reload_config(cfg_b_path)
    get_config(cfg_b_path)  # switch global config

    # cfg_a is stale relative to global state but must still resolve under ext_a
    assert get_path("weather_file", cfg_a) == weather_a
    assert "ext_a" in str(weather_a)


def test_config_loads_with_package_defaults_only(tmp_path: Path) -> None:
    """External projects need no local defaults.yaml."""
    init_project(tmp_path / "ext")
    cfg_path = project_config_path(tmp_path / "ext")
    reload_config(cfg_path)
    from treeheat.config import get_config

    cfg = get_config(cfg_path)
    assert cfg["simulation"]["n_scenarios"] == 25
    assert cfg["model"]["canopy_engine"] == "li2023_ceb"
