"""Config loader and validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from treeheat.config import ConfigError, get_path, reload_config, validate_config


def test_validate_config_passes(valid_config, config_dir: Path) -> None:
    validate_config(valid_config, config_dir=config_dir)


def test_validate_config_missing_key(config_missing_key) -> None:
    config_dir, cfg = config_missing_key
    with pytest.raises(ConfigError, match=r"config\.model\.ceb\.A_coeff"):
        validate_config(cfg, config_dir=config_dir)


def test_validate_config_missing_path(config_missing_path) -> None:
    config_dir, cfg = config_missing_path
    with pytest.raises(ConfigError, match=r"config\.paths\.weather_file"):
        validate_config(cfg, config_dir=config_dir)


def test_get_path_resolves_relative_to_config_dir(config_dir: Path, valid_config) -> None:
    reload_config(config_dir / "config.yaml")
    weather = get_path("weather_file", valid_config)
    assert weather.is_absolute()
    assert weather.name == "weather.epw"
    assert weather.parent.name == "data"


def test_defaults_overridden_by_run_config(config_dir: Path, valid_config) -> None:
    assert valid_config["model"]["canopy_engine"] == "legacy_leaf"
    assert valid_config["analysis"]["period_type"] == "warmest_week"
    assert valid_config["physical_constants"]["sigma"] == 5.67e-8


def test_validate_config_creates_output_dirs(config_dir: Path, valid_config) -> None:
    validate_config(valid_config, config_dir=config_dir)
    outputs_root = config_dir.parent / "outputs"
    assert (outputs_root / "raytracing_results").is_dir()
    assert (outputs_root / "biophysical").is_dir()
    assert (outputs_root / "analysis").is_dir()
