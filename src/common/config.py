"""Configuration loading and management for WikiSeed."""

import os
from pathlib import Path
from typing import Any, Dict

import yaml


def load_config(config_path: str | None = None) -> Dict[str, Any]:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file (default: from CONFIG_PATH env var or ./config.yaml)

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    if config_path is None:
        config_path = os.getenv("CONFIG_PATH", "config.yaml")

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file) as f:
        config = yaml.safe_load(f)

    return config


def get_config_value(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """Get configuration value by dot-separated key path.

    Args:
        config: Configuration dictionary
        key_path: Dot-separated key path (e.g., 'wikiseed.storage.max_storage_gb')
        default: Default value if key not found

    Returns:
        Configuration value or default

    Example:
        >>> config = {'wikiseed': {'storage': {'max_storage_gb': 2000}}}
        >>> get_config_value(config, 'wikiseed.storage.max_storage_gb')
        2000
    """
    keys = key_path.split(".")
    value = config

    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
            if value is None:
                return default
        else:
            return default

    return value
