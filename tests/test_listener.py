"""Tests for the IR listener module."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import EV_KEY, EV_MSC, MSC_SCAN, FakeEvent


# Helper: make async_read_loop return a sequence of FakeEvents
async def _fake_async_read_loop(events):
    for event in events:
        yield event


class TestListen:
    """Tests for the listen() event loop."""

    async def test_power_on_scancode(self, fake_ir_device):
        """IRC-01: Power-on scancode dispatches to mapper on MSC_SCAN."""
        from projector_bridge.listener import listen

        events = [FakeEvent(type=EV_MSC, code=MSC_SCAN, value=0x010015)]
        fake_ir_device.async_read_loop = lambda: _fake_async_read_loop(events)
        mapper = AsyncMock()

        await listen(fake_ir_device, mapper)

        mapper.handle_scancode.assert_called_once_with("0x010015", 1)

    async def test_power_off_scancode(self, fake_ir_device):
        """IRC-02: Power-off scancode dispatches to mapper (same physical button)."""
        from projector_bridge.listener import listen

        events = [FakeEvent(type=EV_MSC, code=MSC_SCAN, value=0x010015)]
        fake_ir_device.async_read_loop = lambda: _fake_async_read_loop(events)
        mapper = AsyncMock()

        await listen(fake_ir_device, mapper)

        mapper.handle_scancode.assert_called_once_with("0x010015", 1)

    async def test_nav_scancodes_repeat(self, fake_ir_device):
        """IRC-03: Each MSC_SCAN event dispatches to mapper."""
        from projector_bridge.listener import listen

        events = [
            FakeEvent(type=EV_MSC, code=MSC_SCAN, value=0x010074),
            FakeEvent(type=EV_MSC, code=MSC_SCAN, value=0x010074),
        ]
        fake_ir_device.async_read_loop = lambda: _fake_async_read_loop(events)
        mapper = AsyncMock()

        await listen(fake_ir_device, mapper)

        assert mapper.handle_scancode.call_count == 2
        mapper.handle_scancode.assert_any_call("0x010074", 1)

    async def test_device_disappearance(self, fake_ir_device):
        """D-06: OSError from device loss raises SystemExit(1)."""
        from projector_bridge.listener import listen

        async def _raise_oserror():
            raise OSError(19, "No such device")
            yield  # make it a generator  # noqa: E305

        fake_ir_device.async_read_loop = _raise_oserror
        mapper = AsyncMock()

        with pytest.raises(SystemExit) as exc_info:
            await listen(fake_ir_device, mapper)
        assert exc_info.value.code == 1

    async def test_non_ir_events_ignored(self, fake_ir_device):
        """Events that are not EV_MSC/MSC_SCAN are silently ignored."""
        from projector_bridge.listener import listen

        events = [
            FakeEvent(type=0, code=0, value=0),  # EV_SYN
            FakeEvent(type=3, code=0, value=100),  # EV_ABS
            FakeEvent(type=EV_KEY, code=116, value=1),  # EV_KEY ignored
        ]
        fake_ir_device.async_read_loop = lambda: _fake_async_read_loop(events)
        mapper = AsyncMock()

        await listen(fake_ir_device, mapper)

        mapper.handle_scancode.assert_not_called()


class TestFindIRDevice:
    """Tests for find_ir_device() polling discovery."""

    async def test_device_found_immediately(self):
        """DEV-03: Device matching name is returned."""
        from projector_bridge.listener import find_ir_device

        mock_device = MagicMock()
        mock_device.name = "gpio_ir_recv"
        mock_device.path = "/dev/input/event3"

        mock_evdev = MagicMock()
        mock_evdev.list_devices.return_value = ["/dev/input/event3"]
        mock_evdev.InputDevice.return_value = mock_device

        with patch.dict(sys.modules, {"evdev": mock_evdev}):
            result = await find_ir_device("gpio_ir_recv", timeout=1.0, poll_interval=0.1)

        assert result.name == "gpio_ir_recv"

    async def test_device_not_found_timeout(self):
        """DEV-03: SystemExit raised when device not found within timeout."""
        from projector_bridge.listener import find_ir_device

        mock_evdev = MagicMock()
        mock_evdev.list_devices.return_value = []

        with patch.dict(sys.modules, {"evdev": mock_evdev}):
            with pytest.raises(SystemExit):
                await find_ir_device("gpio_ir_recv", timeout=0.3, poll_interval=0.1)

    async def test_device_found_on_retry(self):
        """D-05: Device appears on second poll attempt."""
        from projector_bridge.listener import find_ir_device

        mock_device = MagicMock()
        mock_device.name = "gpio_ir_recv"
        mock_device.path = "/dev/input/event3"

        call_count = 0

        def _list_devices():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return []
            return ["/dev/input/event3"]

        mock_evdev = MagicMock()
        mock_evdev.list_devices = _list_devices
        mock_evdev.InputDevice.return_value = mock_device

        with patch.dict(sys.modules, {"evdev": mock_evdev}):
            result = await find_ir_device("gpio_ir_recv", timeout=5.0, poll_interval=0.1)

        assert result.name == "gpio_ir_recv"
        assert call_count == 2

    async def test_non_matching_devices_closed(self):
        """Devices that don't match are closed to avoid fd leak."""
        from projector_bridge.listener import find_ir_device

        wrong_device = MagicMock()
        wrong_device.name = "other_device"
        right_device = MagicMock()
        right_device.name = "gpio_ir_recv"
        right_device.path = "/dev/input/event4"

        mock_evdev = MagicMock()
        mock_evdev.list_devices.return_value = ["/dev/input/event2", "/dev/input/event4"]
        mock_evdev.InputDevice.side_effect = [wrong_device, right_device]

        with patch.dict(sys.modules, {"evdev": mock_evdev}):
            await find_ir_device("gpio_ir_recv", timeout=1.0, poll_interval=0.1)

        wrong_device.close.assert_called_once()
