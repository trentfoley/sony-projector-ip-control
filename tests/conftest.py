"""Shared test fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_config(tmp_path):
    """Yield a helper that writes a YAML string to a temp file and returns its path."""

    def _write(yaml_str: str) -> Path:
        p = tmp_path / "config.yaml"
        p.write_text(yaml_str)
        return p

    return _write


@pytest.fixture
def sample_config_yaml():
    """Return a valid YAML string with all sections populated."""
    return """\
projector:
  host: "192.168.4.100"
  port: 53595
  password: "Projector"
  timeout_connect: 5.0
  timeout_read: 3.0
  retries: 3
  retry_delay: 0.2

mappings:
  "0x010015":
    command: 'power "on"'
    repeat: false
    description: "Power On"
  "0x010074":
    command: 'key "up"'
    repeat: true
    description: "Menu Up"

ir:
  device_name: "gpio_ir_recv"
  protocol: "sony"
"""
