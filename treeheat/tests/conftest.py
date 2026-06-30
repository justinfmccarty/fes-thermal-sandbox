"""Shared pytest fixtures for config and path validation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from treeheat.config import reload_config, validate_config


MINIMAL_DEFAULTS = {
    "model": {
        "canopy_engine": "li2023_ceb",
        "ceb": {
            "enabled": True,
            "A_coeff": 87.0,
            "delta_Tg": 10.0,
            "delta_Tw": 10.0,
            "beta_dir": 0.8,
            "beta_dif": 0.6,
            "epsilon_w": 0.90,
            "epsilon_g_default": 0.95,
            "albedo_g_default": 0.30,
            "T_min_offset": -15.0,
            "T_max_offset": 40.0,
            "solver_xtol": 0.1,
            "solver_maxiter": 50,
        },
        "species_defaults": {"alpha_leaf": 0.18},
        "risk": {"T_crit": 30.0},
        "ground": {"types": {"impervious": {"heat_capacity": 1.0}}},
        "soil": {"theta_fc": 0.35},
    },
    "physical_constants": {
        "sigma": 5.67e-8,
        "rho_air": 1.2,
        "cp_air": 1005.0,
        "lambda_v": 2450000.0,
        "r_gas": 287.0,
    },
    "analysis": {"period_type": "warmest_week"},
}


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Temp config dir with defaults + run config and dummy input files."""
    data_dir = tmp_path / "data"
    grid_dir = data_dir / "grid_records"
    grid_dir.mkdir(parents=True)
    (data_dir / "weather.epw").write_text("PLACEHOLDER", encoding="utf-8")
    (data_dir / "tree_species_database.csv").write_text("species\n", encoding="utf-8")
    (data_dir / "root_material_database.csv").write_text("material\n", encoding="utf-8")
    (grid_dir / ".gitkeep").write_text("", encoding="utf-8")

    cfg_dir = tmp_path / "config"
    _write_yaml(cfg_dir / "defaults.yaml", deepcopy(MINIMAL_DEFAULTS))
    run_cfg = {
        "paths": {
            "weather_file": "../data/weather.epw",
            "species_database_file": "../data/tree_species_database.csv",
            "material_database_file": "../data/root_material_database.csv",
            "grid_records_dir": "../data/grid_records",
            "raytracing_results_dir": "../outputs/raytracing_results",
            "biophysical_outputs_dir": "../outputs/biophysical",
            "analysis_results_dir": "../outputs/analysis",
        },
        "model": {"canopy_engine": "legacy_leaf"},
    }
    _write_yaml(cfg_dir / "config.yaml", run_cfg)
    return cfg_dir


@pytest.fixture
def valid_config(config_dir: Path) -> dict:
    reload_config(config_dir / "config.yaml")
    from treeheat.config import get_config

    return get_config(config_dir / "config.yaml")


@pytest.fixture
def config_missing_key(config_dir: Path) -> tuple[Path, dict]:
    cfg = deepcopy(MINIMAL_DEFAULTS)
    del cfg["model"]["ceb"]["A_coeff"]
    _write_yaml(config_dir / "defaults.yaml", cfg)
    reload_config(config_dir / "config.yaml")
    from treeheat.config import get_config

    return config_dir, get_config(config_dir / "config.yaml")


@pytest.fixture
def config_missing_path(config_dir: Path) -> tuple[Path, dict]:
    run_cfg = {
        "paths": {
            "weather_file": "../data/does_not_exist.epw",
            "species_database_file": "../data/tree_species_database.csv",
            "material_database_file": "../data/root_material_database.csv",
            "grid_records_dir": "../data/grid_records",
        }
    }
    _write_yaml(config_dir / "config.yaml", run_cfg)
    reload_config(config_dir / "config.yaml")
    from treeheat.config import get_config

    return config_dir, get_config(config_dir / "config.yaml")
