"""
Configuration Locator - Single Source of Truth

This module provides the ONLY way to access configuration values.
All parameters must be defined in config.yaml - no hardcoded defaults allowed.

Usage:
    from config_locator import get_config
    
    config = get_config()
    delta_Tg = config.model.ceb.delta_Tg
    T_crit = config.model.risk.T_crit
    period = config.analysis.period_type

Design Principles:
    1. NO FALLBACK DEFAULTS - if a value is missing, raise ConfigError
    2. SINGLETON PATTERN - config loaded once and cached
    3. ATTRIBUTE ACCESS - config.section.subsection.value
    4. VALIDATION ON LOAD - verify required sections exist
"""

import os
import yaml
from typing import Any, Optional, Dict
from pathlib import Path


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""
    pass


class ConfigSection:
    """
    Provides attribute-style access to nested config dictionary.
    
    Raises ConfigError if a key is not found (no silent defaults).
    """
    
    def __init__(self, data: dict, path: str = "config"):
        """
        Initialize config section.
        
        Args:
            data: Dictionary containing config data
            path: Dot-notation path for error messages (e.g., "config.model.ceb")
        """
        object.__setattr__(self, '_data', data)
        object.__setattr__(self, '_path', path)
    
    def __getattr__(self, key: str) -> Any:
        """
        Get config value by attribute name.
        
        Raises ConfigError if key not found.
        """
        # Handle private attributes normally
        if key.startswith('_'):
            return object.__getattribute__(self, key)
        
        data = object.__getattribute__(self, '_data')
        path = object.__getattribute__(self, '_path')
        
        if key not in data:
            raise ConfigError(
                f"Missing required config value: {path}.{key}\n"
                f"Please add '{key}' to the appropriate section in config.yaml"
            )
        
        value = data[key]
        
        # If value is a dict, wrap it in ConfigSection for nested access
        if isinstance(value, dict):
            return ConfigSection(value, f"{path}.{key}")
        
        return value
    
    def __setattr__(self, key: str, value: Any):
        """Prevent modification of config values."""
        if key.startswith('_'):
            object.__setattr__(self, key, value)
        else:
            raise ConfigError("Config values are read-only")
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in config section."""
        return key in self._data
    
    def __repr__(self) -> str:
        return f"ConfigSection({self._path})"
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get config value with optional default.
        
        NOTE: This method exists for backwards compatibility during migration.
        New code should use attribute access which raises ConfigError on missing.
        
        Args:
            key: Config key to look up
            default: Default value if key not found (will log warning)
            
        Returns:
            Config value or default
        """
        try:
            return getattr(self, key)
        except ConfigError:
            if default is not None:
                import warnings
                warnings.warn(
                    f"Using default value for {self._path}.{key}. "
                    f"Add this to config.yaml to suppress this warning.",
                    DeprecationWarning,
                    stacklevel=2
                )
                return default
            raise
    
    def to_dict(self) -> dict:
        """Convert config section back to dictionary."""
        return dict(self._data)
    
    def keys(self):
        """Return keys in this section."""
        return self._data.keys()
    
    def items(self):
        """Return items in this section."""
        return self._data.items()


class Config:
    """
    Main configuration class with singleton pattern.
    
    Loads config.yaml and provides attribute-style access to all values.
    Validates that all required sections exist on load.
    """
    
    _instance: Optional['Config'] = None
    _config_path: Optional[str] = None
    
    # Required top-level sections
    REQUIRED_SECTIONS = ['paths', 'analysis', 'physical_constants', 'model', 'simulation', 'outputs']
    
    # Required model subsections
    REQUIRED_MODEL_SECTIONS = ['ceb', 'species_defaults', 'risk', 'soil']
    
    def __init__(self, data: dict, config_path: str):
        """
        Initialize config from dictionary.
        
        Args:
            data: Parsed YAML config data
            config_path: Path to config file (for error messages)
        """
        self._data = data
        self._config_path = config_path
        self._root = ConfigSection(data, "config")
        
        # Validate on creation
        self._validate()
    
    def _validate(self):
        """
        Validate that all required sections exist.
        
        Raises ConfigError if any required section is missing.
        """
        # Check required top-level sections
        for section in self.REQUIRED_SECTIONS:
            if section not in self._data:
                raise ConfigError(
                    f"Missing required config section: '{section}'\n"
                    f"Config file: {self._config_path}"
                )
        
        # Check required model subsections
        model_data = self._data.get('model', {})
        for subsection in self.REQUIRED_MODEL_SECTIONS:
            if subsection not in model_data:
                raise ConfigError(
                    f"Missing required config section: 'model.{subsection}'\n"
                    f"Config file: {self._config_path}"
                )
    
    def __getattr__(self, key: str) -> Any:
        """Delegate attribute access to root ConfigSection."""
        if key.startswith('_'):
            return object.__getattribute__(self, key)
        return getattr(self._root, key)
    
    @classmethod
    def load(cls, path: Optional[str] = None) -> 'Config':
        """
        Load config from YAML file (singleton pattern).
        
        Args:
            path: Path to config.yaml. If None, searches for config.yaml
                  in current directory and parent directories.
        
        Returns:
            Config instance
            
        Raises:
            ConfigError: If config file not found or invalid
        """
        # Return cached instance if already loaded with same path
        if cls._instance is not None:
            if path is None or path == cls._config_path:
                return cls._instance
            # Different path requested - reload
            cls._instance = None
        
        # Find config file
        if path is None:
            path = cls._find_config()
        
        if not os.path.exists(path):
            raise ConfigError(f"Config file not found: {path}")
        
        # Load YAML
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in config file: {e}")
        
        if data is None:
            raise ConfigError(f"Config file is empty: {path}")
        
        # Create and cache instance
        cls._instance = cls(data, path)
        cls._config_path = path
        
        return cls._instance
    
    @classmethod
    def _find_config(cls) -> str:
        """
        Search for config.yaml in current and parent directories.
        
        Returns:
            Path to config.yaml
            
        Raises:
            ConfigError: If config.yaml not found
        """
        # Start from current working directory
        current = Path.cwd()
        
        # Also check the directory containing this module
        module_dir = Path(__file__).parent
        
        # Search paths in order of preference
        search_paths = [
            current / 'config.yaml',
            module_dir / 'config.yaml',
            current.parent / 'config.yaml',
            module_dir.parent / 'config.yaml',
        ]
        
        for path in search_paths:
            if path.exists():
                return str(path)
        
        raise ConfigError(
            f"config.yaml not found. Searched:\n" +
            "\n".join(f"  - {p}" for p in search_paths)
        )
    
    @classmethod
    def reload(cls, path: Optional[str] = None) -> 'Config':
        """
        Force reload of config file.
        
        Useful for testing or when config file has been modified.
        
        Args:
            path: Path to config.yaml (optional)
            
        Returns:
            New Config instance
        """
        cls._instance = None
        cls._config_path = None
        return cls.load(path)
    
    def to_dict(self) -> dict:
        """Return config as dictionary."""
        return dict(self._data)


def get_config(path: Optional[str] = None) -> Config:
    """
    Get the global config instance.
    
    This is the ONLY way to access configuration values.
    
    Args:
        path: Optional path to config.yaml
        
    Returns:
        Config instance
        
    Example:
        config = get_config()
        delta_Tg = config.model.ceb.delta_Tg
        T_crit = config.model.risk.T_crit
    """
    return Config.load(path)


def reload_config(path: Optional[str] = None) -> Config:
    """
    Force reload of config file.
    
    Use when config.yaml has been modified and needs to be re-read.
    
    Args:
        path: Optional path to config.yaml
        
    Returns:
        New Config instance
    """
    return Config.reload(path)


# =============================================================================
# Utility Functions for Common Config Patterns
# =============================================================================

def resolve_config_path(path_value: str) -> str:
    """
    Resolve a path from config, handling relative paths.
    
    This enables cross-platform compatibility between macOS and Windows:
    - Absolute paths: returned normalized for current platform
    - Relative paths: resolved against config.yaml directory
    
    Args:
        path_value: Path string from config (absolute or relative)
        
    Returns:
        Resolved, platform-native path string
    """
    path = Path(path_value)
    
    if path.is_absolute():
        # Absolute path - just normalize for current platform
        return str(path)
    
    # Relative path - resolve against config file location
    config_dir = Path(Config._config_path).parent
    resolved = (config_dir / path).resolve()
    return str(resolved)


def get_path(key: str) -> str:
    """
    Get a path from config.paths section, resolved for current platform.
    
    Handles both absolute and relative paths:
    - Absolute paths are returned as-is (normalized)
    - Relative paths are resolved against the config.yaml directory
    
    Args:
        key: Path key (e.g., 'weather_file', 'project_root')
        
    Returns:
        Resolved, platform-native path string
    """
    config = get_config()
    path_value = getattr(config.paths, key)
    return resolve_config_path(path_value)


def get_physical_constant(key: str) -> float:
    """
    Get a physical constant.
    
    Args:
        key: Constant key (e.g., 'sigma', 'rho_air')
        
    Returns:
        Constant value
    """
    config = get_config()
    return getattr(config.physical_constants, key)


def get_ceb_param(key: str) -> Any:
    """
    Get a CEB model parameter.
    
    Args:
        key: Parameter key (e.g., 'delta_Tg', 'A_coeff')
        
    Returns:
        Parameter value
    """
    config = get_config()
    return getattr(config.model.ceb, key)


def get_species_default(key: str) -> Any:
    """
    Get a species default parameter.
    
    Args:
        key: Parameter key (e.g., 'alpha_leaf', 'r_sto')
        
    Returns:
        Default value
    """
    config = get_config()
    return getattr(config.model.species_defaults, key)


def get_risk_param(key: str) -> Any:
    """
    Get a risk threshold parameter.
    
    Args:
        key: Parameter key (e.g., 'T_crit', 'vpd_threshold')
        
    Returns:
        Parameter value
    """
    config = get_config()
    return getattr(config.model.risk, key)


def is_ceb_enabled() -> bool:
    """Check if CEB model is enabled."""
    config = get_config()
    return config.model.ceb.enabled
