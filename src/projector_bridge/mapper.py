"""Command mapper: translates IR scancodes into ADCP commands."""

import asyncio
import logging

from projector_bridge.adcp import send_command_with_retry
from projector_bridge.config import Config
from projector_bridge.errors import ADCPError

log = logging.getLogger(__name__)

# Minimum interval between ADCP sends in seconds
_RATE_LIMIT_SECONDS = 0.25


class CommandMapper:
    """Translates IR scancodes into ADCP commands with repeat filtering and rate limiting.

    Takes a Config instance at init and exposes a single public method
    ``handle_scancode()`` that Phase 3's evdev listener calls per IR event.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._last_send_time: float = 0.0
        self._previous_values: dict[str, str] = {}

    async def handle_scancode(self, scancode: str, event_value: int) -> None:
        """Process a single IR scancode event.

        Args:
            scancode: Hex scancode string (key in config mappings dict).
            event_value: evdev event value — 0=key-up, 1=key-down, 2=repeat.
        """
        # D-02: Ignore key-up events
        if event_value == 0:
            return

        # Lookup scancode in mappings
        mapping = self._config.mappings.get(scancode)
        if mapping is None:
            # D-07: Log unknown scancodes at INFO
            log.info("Unknown scancode: %s", scancode)
            return

        # D-01: key-down (1) always fires; repeat (2) only if mapping.repeat is True
        if event_value == 2 and not mapping.repeat:
            return

        # D-03: Global rate limit — lossy drop
        now = asyncio.get_event_loop().time()
        if now - self._last_send_time < _RATE_LIMIT_SECONDS:
            log.debug(
                "Rate limited: %s (%.3fs since last send)",
                scancode,
                now - self._last_send_time,
            )
            return

        self._last_send_time = now

        # Fire-and-forget ADCP send
        asyncio.create_task(self._send(mapping.command, scancode))

    async def _send(self, command: str, scancode: str) -> None:
        """Send an ADCP command, logging errors without propagating.

        Handles special commands that require query-then-set logic.
        """
        try:
            if command == "power_toggle":
                await self._power_toggle(scancode)
            elif command == "input_toggle":
                await self._input_toggle(scancode)
            elif command.endswith("_up") or command.endswith("_down"):
                await self._adjust(command, scancode)
            elif command.endswith("_toggle"):
                await self._setting_toggle(command, scancode)
            else:
                await send_command_with_retry(self._config.projector, command)
                log.debug("Sent ADCP command: %s (scancode: %s)", command, scancode)
        except ADCPError as e:
            log.error("ADCP error for scancode %s: %s", scancode, e)

    async def _power_toggle(self, scancode: str) -> None:
        """Query power status and send the appropriate power command."""
        status = await send_command_with_retry(
            self._config.projector, 'power_status ?'
        )
        log.debug("Power status: %s (scancode: %s)", status, scancode)

        if status in ("standby", "saving_standby"):
            await send_command_with_retry(self._config.projector, 'power "on"')
            log.info("Power ON (was %s)", status)
        elif status in ("on", "startup"):
            await send_command_with_retry(self._config.projector, 'power "off"')
            log.info("Power OFF (was %s)", status)
        else:
            log.info("Power toggle ignored — projector is %s", status)

    async def _input_toggle(self, scancode: str) -> None:
        """Toggle between hdmi1 and hdmi2."""
        current = await send_command_with_retry(
            self._config.projector, 'input ?'
        )
        target = "hdmi2" if current == "hdmi1" else "hdmi1"
        await send_command_with_retry(
            self._config.projector, f'input "{target}"'
        )
        log.info("Input: %s -> %s", current, target)

    async def _adjust(self, command: str, scancode: str) -> None:
        """Query current value, increment/decrement by 1, and set.

        Command format: 'brightness_up', 'contrast_down', etc.
        """
        if command.endswith("_up"):
            setting = command[:-3]
            delta = 1
        else:
            setting = command[:-5]
            delta = -1

        raw = await send_command_with_retry(
            self._config.projector, f'{setting} ?'
        )
        try:
            current = int(raw)
        except (ValueError, TypeError):
            log.error("Cannot parse %s value: %s", setting, raw)
            return

        new_val = max(0, min(100, current + delta))
        if new_val == current:
            log.debug("%s already at limit: %d", setting, current)
            return

        await send_command_with_retry(
            self._config.projector, f'{setting} {new_val}'
        )
        log.info("%s: %d -> %d", setting, current, new_val)

    async def _setting_toggle(self, command: str, scancode: str) -> None:
        """Toggle a setting between states.

        Command format: 'real_cre_toggle', 'motionflow_toggle', 'hdr_toggle'.
        Remembers the previous non-off value so toggling back restores it.
        """
        setting = command[:-7]  # strip '_toggle'
        current = await send_command_with_retry(
            self._config.projector, f'{setting} ?'
        )

        if current == "off":
            # Restore previous value, or use sensible defaults
            target = self._previous_values.get(setting, "on")
        else:
            # Save current value before turning off
            self._previous_values[setting] = current
            target = "off"

        await send_command_with_retry(
            self._config.projector, f'{setting} "{target}"'
        )
        log.info("%s: %s -> %s", setting, current, target)
