"""Shared test fixtures."""

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


@dataclass
class FakeEvent:
    """Mock evdev event with type, code, value attributes."""
    type: int
    code: int
    value: int


# evdev ecodes constants (Linux input event types)
EV_KEY = 1
EV_MSC = 4
MSC_SCAN = 4


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


@pytest.fixture
def fake_ir_device():
    """Return a mock evdev InputDevice with configurable async_read_loop."""
    device = MagicMock()
    device.name = "gpio_ir_recv"
    device.path = "/dev/input/event3"
    device.close = MagicMock()
    return device


@pytest.fixture
def make_events():
    """Factory: create a standard IR button press event sequence.

    Returns (MSC_SCAN with raw scancode, EV_KEY with key state).
    """
    def _make(scancode_int: int, key_value: int, keycode: int = 0):
        return [
            FakeEvent(type=EV_MSC, code=MSC_SCAN, value=scancode_int),
            FakeEvent(type=EV_KEY, code=keycode, value=key_value),
        ]
    return _make
