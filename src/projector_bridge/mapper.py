"""Command mapper: translates IR scancodes into ADCP commands."""

import asyncio
import logging

from projector_bridge.adcp import send_command_with_retry
from projector_bridge.config import Config
from projector_bridge.errors import ADCPError

log = logging.getLogger(__name__)

# Minimum interval between ADCP sends in seconds
_RATE_LIMIT_SECONDS = 0.1


class CommandMapper:
    """Translates IR scancodes into ADCP commands with repeat filtering and rate limiting.

    Takes a Config instance at init and exposes a single public method
    ``handle_scancode()`` that Phase 3's evdev listener calls per IR event.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._last_send_time: float = 0.0

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

        Handles special command "power_toggle" by querying power_status first.
        """
        try:
            if command == "power_toggle":
                await self._power_toggle(scancode)
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

        # States where we should turn on
        if status in ("standby", "saving_standby"):
            await send_command_with_retry(self._config.projector, 'power "on"')
            log.info("Power ON (was %s)", status)
        # States where we should turn off
        elif status in ("on", "startup"):
            await send_command_with_retry(self._config.projector, 'power "off"')
            log.info("Power OFF (was %s)", status)
        # Cooling/transitional states — ignore
        else:
            log.info("Power toggle ignored — projector is %s", status)
