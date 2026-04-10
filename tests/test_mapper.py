"""Tests for CommandMapper: debounce, repeat, rate limiting, and error handling."""

import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest

from projector_bridge.config import CommandMapping, Config, IRConfig, ProjectorConfig
from projector_bridge.errors import ADCPError
from projector_bridge.mapper import CommandMapper


def _make_mapper(mappings=None):
    """Build a CommandMapper with test config and mocked ADCP send."""
    if mappings is None:
        mappings = {
            "0x010015": CommandMapping(command='power "on"', repeat=False, description="Power On"),
            "0x010074": CommandMapping(command='key "up"', repeat=True, description="Menu Up"),
        }
    config = Config(
        projector=ProjectorConfig(host="127.0.0.1", port=53595, password="test"),
        mappings=mappings,
        ir=IRConfig(),
    )
    return CommandMapper(config)


async def _drain_tasks():
    """Let any pending create_task callbacks run to completion."""
    await asyncio.sleep(0)
    await asyncio.sleep(0)


# --- MAP-02: Non-repeat keydown fires command ---


async def test_keydown_fires_command():
    """MAP-02: event_value=1 with mapped non-repeat scancode calls send exactly once."""
    mapper = _make_mapper()
    with patch(
        "projector_bridge.mapper.send_command_with_retry", new_callable=AsyncMock
    ) as mock_send:
        await mapper.handle_scancode("0x010015", 1)
        await _drain_tasks()
        mock_send.assert_called_once_with(mapper._config.projector, 'power "on"')


# --- D-02: Key-up events are ignored ---


async def test_keyup_ignored():
    """D-02: event_value=0 never calls send."""
    mapper = _make_mapper()
    with patch(
        "projector_bridge.mapper.send_command_with_retry", new_callable=AsyncMock
    ) as mock_send:
        await mapper.handle_scancode("0x010015", 0)
        await _drain_tasks()
        mock_send.assert_not_called()


# --- MAP-02: Non-repeat ignores hold (event_value=2) ---


async def test_non_repeat_ignores_hold():
    """MAP-02: event_value=2 with repeat=False mapping does NOT call send."""
    mapper = _make_mapper()
    with patch(
        "projector_bridge.mapper.send_command_with_retry", new_callable=AsyncMock
    ) as mock_send:
        await mapper.handle_scancode("0x010015", 2)
        await _drain_tasks()
        mock_send.assert_not_called()


# --- MAP-03: Repeat-enabled mapping fires on hold ---


async def test_repeat_fires_on_hold():
    """MAP-03: event_value=2 with repeat=True mapping DOES call send."""
    mapper = _make_mapper()
    with patch(
        "projector_bridge.mapper.send_command_with_retry", new_callable=AsyncMock
    ) as mock_send:
        await mapper.handle_scancode("0x010074", 2)
        await _drain_tasks()
        mock_send.assert_called_once_with(mapper._config.projector, 'key "up"')


# --- MAP-04: Unknown scancode logged at INFO ---


async def test_unknown_scancode_logged(caplog):
    """MAP-04: unmapped scancode logs at INFO with hex value, no send called."""
    mapper = _make_mapper()
    with patch(
        "projector_bridge.mapper.send_command_with_retry", new_callable=AsyncMock
    ) as mock_send:
        with caplog.at_level(logging.INFO, logger="projector_bridge.mapper"):
            await mapper.handle_scancode("0xFFFFFF", 1)
            await _drain_tasks()
        mock_send.assert_not_called()
    assert "Unknown scancode: 0xFFFFFF" in caplog.text


# --- MAP-05: Rate limit drops rapid sends ---


async def test_rate_limit_drops_rapid_sends():
    """MAP-05: two handle_scancode calls within 100ms -- first fires, second dropped."""
    mapper = _make_mapper()
    with patch(
        "projector_bridge.mapper.send_command_with_retry", new_callable=AsyncMock
    ) as mock_send:
        # First call fires
        await mapper.handle_scancode("0x010015", 1)
        await _drain_tasks()
        assert mock_send.call_count == 1

        # Set last_send_time to now so next call is within rate limit window
        mapper._last_send_time = asyncio.get_event_loop().time()
        await mapper.handle_scancode("0x010074", 2)
        await _drain_tasks()
        # Still only 1 call -- second was rate-limited
        assert mock_send.call_count == 1


# --- MAP-05: Rate limit allows after interval ---


async def test_rate_limit_allows_after_interval():
    """MAP-05: two calls with >100ms gap -- both fire."""
    mapper = _make_mapper()
    with patch(
        "projector_bridge.mapper.send_command_with_retry", new_callable=AsyncMock
    ) as mock_send:
        await mapper.handle_scancode("0x010015", 1)
        await _drain_tasks()
        assert mock_send.call_count == 1

        # Push last_send_time back so it appears >100ms has passed
        mapper._last_send_time = asyncio.get_event_loop().time() - 0.2
        await mapper.handle_scancode("0x010074", 2)
        await _drain_tasks()
        assert mock_send.call_count == 2


# --- ADCPError is caught and logged, not raised ---


async def test_adcp_error_logged_not_raised(caplog):
    """ADCPError in send is caught and logged, does not propagate."""
    mapper = _make_mapper()
    with patch(
        "projector_bridge.mapper.send_command_with_retry",
        new_callable=AsyncMock,
        side_effect=ADCPError("connection failed"),
    ):
        with caplog.at_level(logging.ERROR, logger="projector_bridge.mapper"):
            await mapper.handle_scancode("0x010015", 1)
            await _drain_tasks()
    assert "ADCP error" in caplog.text
    assert "connection failed" in caplog.text


# --- First command always fires (last_send_time starts at 0) ---


async def test_first_command_always_fires():
    """First command fires regardless of timing -- last_send_time starts at 0."""
    mapper = _make_mapper()
    # Verify initial state
    assert mapper._last_send_time == 0.0
    with patch(
        "projector_bridge.mapper.send_command_with_retry", new_callable=AsyncMock
    ) as mock_send:
        await mapper.handle_scancode("0x010015", 1)
        await _drain_tasks()
        mock_send.assert_called_once()
        # last_send_time should now be updated
        assert mapper._last_send_time > 0.0


# --- Power toggle ---


async def test_power_toggle_turns_on_from_standby():
    """power_toggle sends power "on" when projector is in standby."""
    mapper = _make_mapper(
        {"0x540015": CommandMapping(command="power_toggle", description="Power")}
    )
    with patch(
        "projector_bridge.mapper.send_command_with_retry", new_callable=AsyncMock
    ) as mock_send:
        mock_send.side_effect = ["standby", "ok"]
        await mapper.handle_scancode("0x540015", 1)
        await _drain_tasks()
        assert mock_send.call_count == 2
        mock_send.assert_any_call(mapper._config.projector, 'power_status ?')
        mock_send.assert_any_call(mapper._config.projector, 'power "on"')


async def test_power_toggle_turns_off_from_on():
    """power_toggle sends power "off" when projector is on."""
    mapper = _make_mapper(
        {"0x540015": CommandMapping(command="power_toggle", description="Power")}
    )
    with patch(
        "projector_bridge.mapper.send_command_with_retry", new_callable=AsyncMock
    ) as mock_send:
        mock_send.side_effect = ["on", "ok"]
        await mapper.handle_scancode("0x540015", 1)
        await _drain_tasks()
        assert mock_send.call_count == 2
        mock_send.assert_any_call(mapper._config.projector, 'power_status ?')
        mock_send.assert_any_call(mapper._config.projector, 'power "off"')


async def test_power_toggle_turns_on_from_saving_standby():
    """power_toggle sends power "on" from saving_standby state."""
    mapper = _make_mapper(
        {"0x540015": CommandMapping(command="power_toggle", description="Power")}
    )
    with patch(
        "projector_bridge.mapper.send_command_with_retry", new_callable=AsyncMock
    ) as mock_send:
        mock_send.side_effect = ["saving_standby", "ok"]
        await mapper.handle_scancode("0x540015", 1)
        await _drain_tasks()
        mock_send.assert_any_call(mapper._config.projector, 'power "on"')


async def test_power_toggle_ignored_during_cooling():
    """power_toggle does nothing when projector is cooling."""
    mapper = _make_mapper(
        {"0x540015": CommandMapping(command="power_toggle", description="Power")}
    )
    with patch(
        "projector_bridge.mapper.send_command_with_retry", new_callable=AsyncMock
    ) as mock_send:
        mock_send.return_value = "cooling1"
        await mapper.handle_scancode("0x540015", 1)
        await _drain_tasks()
        # Only the status query, no power command
        mock_send.assert_called_once_with(mapper._config.projector, 'power_status ?')


async def test_power_toggle_turns_off_from_startup():
    """power_toggle sends power "off" when projector is starting up."""
    mapper = _make_mapper(
        {"0x540015": CommandMapping(command="power_toggle", description="Power")}
    )
    with patch(
        "projector_bridge.mapper.send_command_with_retry", new_callable=AsyncMock
    ) as mock_send:
        mock_send.side_effect = ["startup", "ok"]
        await mapper.handle_scancode("0x540015", 1)
        await _drain_tasks()
        mock_send.assert_any_call(mapper._config.projector, 'power "off"')
