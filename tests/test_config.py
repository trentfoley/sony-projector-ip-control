"""Tests for the config loading and validation system."""

import pytest

from projector_bridge.config import load_config
from projector_bridge.errors import ConfigError


def test_load_valid_config(tmp_config, sample_config_yaml):
    path = tmp_config(sample_config_yaml)
    config = load_config(path)

    assert config.projector.host == "192.168.4.100"
    assert config.projector.port == 53595
    assert config.projector.password == "Projector"
    assert len(config.mappings) == 2
    assert config.mappings["0x010015"].command == 'power "on"'
    assert config.ir.device_name == "gpio_ir_recv"


def test_load_config_defaults(tmp_config):
    yaml_str = """\
projector:
  host: "10.0.0.1"
  password: "test"
"""
    config = load_config(tmp_config(yaml_str))

    assert config.projector.port == 53595
    assert config.projector.timeout_connect == 5.0
    assert config.projector.retries == 3
    assert config.mappings == {}
    assert config.ir.device_name == "gpio_ir_recv"


def test_load_config_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nonexistent.yaml")


def test_load_config_empty_file(tmp_config):
    with pytest.raises(ConfigError, match="empty"):
        load_config(tmp_config(""))


def test_load_config_invalid_yaml(tmp_config):
    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_config(tmp_config("[[["))


def test_load_config_missing_projector_section(tmp_config):
    yaml_str = """\
ir:
  device_name: "test"
"""
    with pytest.raises(ConfigError, match="projector"):
        load_config(tmp_config(yaml_str))


def test_load_config_missing_host(tmp_config):
    yaml_str = """\
projector:
  password: "test"
"""
    with pytest.raises(ConfigError, match="host"):
        load_config(tmp_config(yaml_str))


def test_load_config_mapping_missing_command(tmp_config):
    yaml_str = """\
projector:
  host: "10.0.0.1"
mappings:
  "0x01":
    description: "Missing command field"
"""
    with pytest.raises(ConfigError, match="command"):
        load_config(tmp_config(yaml_str))
