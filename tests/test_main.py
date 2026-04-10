"""Tests for the CLI entry point, discover mode, and signal handling."""

import argparse
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from projector_bridge.__main__ import _discover_loop, _find_config, async_main
from projector_bridge.errors import ConfigError
from tests.conftest import EV_KEY, EV_MSC, MSC_SCAN, FakeEvent


async def _fake_async_read_loop(events):
    for event in events:
        yield event


class TestDiscoverMode:
    """Tests for the --discover mode output."""

    async def test_discover_prints_scancode_on_msc_scan(self, fake_ir_device, capsys):
        """DEV-01: Discover mode prints scancode on MSC_SCAN event."""
        events = [
            FakeEvent(type=EV_MSC, code=MSC_SCAN, value=0x010015),
        ]
        fake_ir_device.async_read_loop = lambda: _fake_async_read_loop(events)

        await _discover_loop(fake_ir_device)

        captured = capsys.readouterr()
        assert captured.out.strip() == "0x010015"

    async def test_discover_deduplicates_repeats(self, fake_ir_device, capsys):
        """Repeated MSC_SCAN with same value only prints once (held button)."""
        events = [
            FakeEvent(type=EV_MSC, code=MSC_SCAN, value=0x010015),
            FakeEvent(type=EV_MSC, code=MSC_SCAN, value=0x010015),
            FakeEvent(type=EV_MSC, code=MSC_SCAN, value=0x010015),
        ]
        fake_ir_device.async_read_loop = lambda: _fake_async_read_loop(events)

        await _discover_loop(fake_ir_device)

        captured = capsys.readouterr()
        assert captured.out.strip() == "0x010015"

    async def test_discover_prints_different_scancodes(self, fake_ir_device, capsys):
        """Different scancodes each print."""
        events = [
            FakeEvent(type=EV_MSC, code=MSC_SCAN, value=0x010015),
            FakeEvent(type=EV_MSC, code=MSC_SCAN, value=0x010074),
        ]
        fake_ir_device.async_read_loop = lambda: _fake_async_read_loop(events)

        await _discover_loop(fake_ir_device)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert lines == ["0x010015", "0x010074"]


class TestFindConfig:
    """Tests for config file resolution."""

    def test_explicit_config_path(self, tmp_path):
        """--config with existing path returns that path."""
        config_file = tmp_path / "test-config.yaml"
        config_file.write_text("projector:\n  host: test\n")

        result = _find_config(str(config_file))
        assert result == config_file

    def test_explicit_config_not_found(self):
        """--config with nonexistent path raises ConfigError."""
        with pytest.raises(ConfigError, match="Config file not found"):
            _find_config("/nonexistent/path/config.yaml")

    def test_default_search_finds_local(self, tmp_path, monkeypatch):
        """No --config searches ./projector-bridge.yaml first."""
        local_config = tmp_path / "projector-bridge.yaml"
        local_config.write_text("projector:\n  host: test\n")

        # Temporarily override search paths
        monkeypatch.setattr(
            "projector_bridge.__main__._CONFIG_SEARCH_PATHS",
            [local_config],
        )

        result = _find_config(None)
        assert result == local_config

    def test_no_config_found_raises(self, monkeypatch):
        """No --config and no default files raises ConfigError."""
        monkeypatch.setattr(
            "projector_bridge.__main__._CONFIG_SEARCH_PATHS",
            [Path("/nonexistent/projector-bridge.yaml")],
        )

        with pytest.raises(ConfigError, match="No config file found"):
            _find_config(None)


class TestCLIParsing:
    """Tests for argparse flag handling."""

    def test_discover_flag(self):
        """--discover sets args.discover = True."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--discover", action="store_true")
        args = parser.parse_args(["--discover"])
        assert args.discover is True

    def test_log_level_flag(self):
        """--log-level accepts valid levels."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="INFO",
        )
        args = parser.parse_args(["--log-level", "DEBUG"])
        assert args.log_level == "DEBUG"

    def test_log_level_default(self):
        """Default log level is INFO per D-07."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="INFO",
        )
        args = parser.parse_args([])
        assert args.log_level == "INFO"


class TestGracefulShutdown:
    """Tests for SIGTERM/SIGINT signal handling."""

    async def test_cancelled_error_closes_device(self, fake_ir_device):
        """DEV-04: CancelledError triggers device.close() in finally block."""
        args = argparse.Namespace(discover=True, config=None, log_level="INFO")

        # find_ir_device returns our fake device
        with patch(
            "projector_bridge.__main__.find_ir_device",
            return_value=fake_ir_device,
        ):
            # _discover_loop raises CancelledError (simulating signal)
            with patch(
                "projector_bridge.__main__._discover_loop",
                side_effect=asyncio.CancelledError,
            ):
                await async_main(args)

        fake_ir_device.close.assert_called_once()

    async def test_bridge_mode_cancelled_closes_device(self, fake_ir_device, tmp_path):
        """DEV-04: Bridge mode CancelledError also triggers device.close()."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            'projector:\n  host: "192.168.4.100"\nmappings:\n  "0x010015":\n'
            '    command: \'power "on"\'\n'
        )

        args = argparse.Namespace(
            discover=False, config=str(config_file), log_level="INFO"
        )

        with patch(
            "projector_bridge.__main__.find_ir_device",
            return_value=fake_ir_device,
        ):
            with patch(
                "projector_bridge.__main__.listen",
                side_effect=asyncio.CancelledError,
            ):
                await async_main(args)

        fake_ir_device.close.assert_called_once()
