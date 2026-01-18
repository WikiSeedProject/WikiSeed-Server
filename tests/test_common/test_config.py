"""Tests for configuration loading."""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.common.config import get_config_value, load_config


def test_load_config():
    """Test loading configuration from YAML file."""
    # Create temporary config file
    config_data = {
        "wikiseed": {
            "storage": {"max_storage_gb": 2000},
            "download": {"max_retries": 5},
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config = load_config(config_path)
        assert config == config_data
        assert config["wikiseed"]["storage"]["max_storage_gb"] == 2000
    finally:
        Path(config_path).unlink()


def test_load_config_not_found():
    """Test loading non-existent config file raises error."""
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/config.yaml")


def test_get_config_value(sample_config):
    """Test getting config value by key path."""
    value = get_config_value(sample_config, "wikiseed.storage.max_storage_gb")
    assert value == 100


def test_get_config_value_default(sample_config):
    """Test getting non-existent config value returns default."""
    value = get_config_value(sample_config, "wikiseed.nonexistent.key", default=42)
    assert value == 42


def test_get_config_value_none(sample_config):
    """Test getting non-existent config value returns None."""
    value = get_config_value(sample_config, "wikiseed.nonexistent.key")
    assert value is None
