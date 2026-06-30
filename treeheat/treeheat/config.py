"""Configuration access — the ONLY sanctioned source of parameters and paths.

PORT FROM: src_archive/config_locator.py (principle was right; enforce it everywhere).

Contract:
  - Two layers: config/defaults.yaml (defaults) overridden by config/config.yaml (run).
  - get_config() / get_path() are the only public accessors. No hardcoded defaults
    anywhere else in the codebase.
  - validate_config() runs at startup: fails LOUDLY on missing keys or non-existent
    paths. Relative paths resolve against the config-file directory (portable).
"""
from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "ConfigError",
    "get_config",
    "get_config_path",
    "get_path",
    "packaged_defaults_path",
    "reload_config",
    "validate_config",
]

REQUIRED_TOP_LEVEL = ("paths", "analysis", "physical_constants", "model")
REQUIRED_MODEL_SECTIONS = ("ceb", "species_defaults", "risk", "ground", "soil")
REQUIRED_PATH_KEYS = (
    "weather_file",
    "species_database_file",
    "material_database_file",
    "grid_records_dir",
)
OUTPUT_PATH_KEYS = (
    "raytracing_results_dir",
    "biophysical_outputs_dir",
    "analysis_results_dir",
)

_config_cache: dict[str, Any] | None = None
_config_dir: Path | None = None
_config_path: Path | None = None
_cfg_roots: dict[int, Path] = {}


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base; override wins on conflicts."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def packaged_defaults_path() -> Path:
    """Absolute path to package-shipped defaults.yaml (single source of truth)."""
    return Path(resources.files("treeheat") / "defaults.yaml")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in config file {path}: {exc}") from exc
    if data is None:
        raise ConfigError(f"Config file is empty: {path}")
    if not isinstance(data, dict):
        raise ConfigError(f"Config file must contain a YAML mapping: {path}")
    return data


def _resolve_config_path(path: str | Path | None) -> Path:
    if path is not None:
        return Path(path).resolve()
    candidate = Path.cwd() / "config" / "config.yaml"
    if candidate.exists():
        return candidate.resolve()
    raise ConfigError(
        "config.yaml not found. Pass an explicit path to get_config() or run from "
        "the project directory containing config/config.yaml."
    )


def _resolve_path_value(path_value: str | Path, config_dir: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path.resolve()
    return (config_dir / path).resolve()


def _require_section(cfg: dict[str, Any], section: str, parent: str = "config") -> dict[str, Any]:
    if section not in cfg:
        raise ConfigError(
            f"Missing required config section: '{parent}.{section}'\n"
            f"Please add the '{section}' section to your config files."
        )
    value = cfg[section]
    if not isinstance(value, dict):
        raise ConfigError(
            f"Config section '{parent}.{section}' must be a mapping, got {type(value).__name__}"
        )
    return value


def _require_key(section: dict[str, Any], key: str, dotted_path: str) -> Any:
    if key not in section:
        raise ConfigError(
            f"Missing required config value: {dotted_path}\n"
            f"Please add '{key}' to the appropriate section in config files."
        )
    return section[key]


def get_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load merged defaults + run config as a dict."""
    global _config_cache, _config_dir, _config_path

    run_path = _resolve_config_path(path)
    if _config_cache is not None and _config_path == run_path:
        return _config_cache

    config_dir = run_path.parent
    defaults_path = config_dir / "defaults.yaml"
    if defaults_path.exists():
        defaults = _load_yaml(defaults_path)
    else:
        defaults = _load_yaml(packaged_defaults_path())
    run_cfg = _load_yaml(run_path)
    merged = _deep_merge(defaults, run_cfg)

    _config_cache = merged
    _config_dir = config_dir
    _config_path = run_path
    _cfg_roots[id(merged)] = config_dir
    return merged


def reload_config(path: str | Path | None = None) -> dict[str, Any]:
    """Force reload of config files (useful in tests)."""
    global _config_cache, _config_dir, _config_path
    _config_cache = None
    _config_dir = None
    _config_path = None
    return get_config(path)


def get_config_path() -> Path | None:
    """Absolute path to the loaded run config file, if get_config() was called."""
    return _config_path


def get_path(key: str, cfg: dict[str, Any] | None = None, *, config_dir: Path | None = None) -> Path:
    """Resolve a config path key to an absolute Path."""
    if cfg is None:
        cfg = get_config()
    base = config_dir
    if base is None:
        base = _cfg_roots.get(id(cfg))
    if base is None:
        base = _config_dir
    if base is None and _config_path is not None:
        base = _config_path.parent
    if base is None:
        raise ConfigError("Config directory is not set. Call get_config() first.")
    paths = _require_section(cfg, "paths")
    path_value = _require_key(paths, key, f"config.paths.{key}")
    return _resolve_path_value(path_value, base)


def validate_config(cfg: dict[str, Any], *, config_dir: Path | None = None) -> None:
    """Fail loudly on missing keys / missing input files."""
    if config_dir is None:
        if _config_dir is None:
            raise ConfigError("validate_config() requires config_dir when get_config() was not called.")
        config_dir = _config_dir

    for section in REQUIRED_TOP_LEVEL:
        _require_section(cfg, section)

    model = _require_section(cfg, "model")
    for subsection in REQUIRED_MODEL_SECTIONS:
        _require_section(model, subsection, parent="config.model")

    _require_key(model, "canopy_engine", "config.model.canopy_engine")

    physical_constants = _require_section(cfg, "physical_constants")
    for key in ("sigma", "rho_air", "cp_air", "lambda_v", "r_gas"):
        _require_key(physical_constants, key, f"config.physical_constants.{key}")

    ceb = _require_section(model, "ceb", parent="config.model")
    for key in (
        "enabled",
        "A_coeff",
        "delta_Tg",
        "delta_Tw",
        "beta_dir",
        "beta_dif",
        "epsilon_w",
        "epsilon_g_default",
        "albedo_g_default",
        "T_min_offset",
        "T_max_offset",
        "solver_xtol",
        "solver_maxiter",
    ):
        _require_key(ceb, key, f"config.model.ceb.{key}")

    paths = _require_section(cfg, "paths")
    for key in REQUIRED_PATH_KEYS:
        path_value = _require_key(paths, key, f"config.paths.{key}")
        resolved = _resolve_path_value(path_value, config_dir)
        if not resolved.exists():
            raise ConfigError(
                f"Missing required input path: config.paths.{key}\n"
                f"Resolved to: {resolved}\n"
                f"Please create the file/directory or update config.paths.{key}."
            )

    for key in OUTPUT_PATH_KEYS:
        if key not in paths:
            continue
        resolved = _resolve_path_value(paths[key], config_dir)
        resolved.mkdir(parents=True, exist_ok=True)
