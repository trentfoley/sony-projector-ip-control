"""evdev IR listener: device discovery and async event loop."""

import asyncio
import logging

log = logging.getLogger(__name__)

# Linux input event type constants (avoid importing evdev on non-Linux)
EV_KEY = 1
EV_MSC = 4
MSC_SCAN = 4


async def find_ir_device(device_name: str, timeout: float = 30.0, poll_interval: float = 2.0):
    """Poll for an evdev InputDevice matching device_name.

    Args:
        device_name: Expected device.name string (e.g. "gpio_ir_recv").
        timeout: Maximum seconds to wait.
        poll_interval: Seconds between polls.

    Returns:
        evdev.InputDevice for the matched device.

    Raises:
        SystemExit: If device not found within timeout.
    """
    import evdev

    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while True:
        for path in evdev.list_devices():
            dev = evdev.InputDevice(path)
            if dev.name == device_name:
                log.info("Found IR device: %s at %s", device_name, dev.path)
                return dev
            dev.close()
        if loop.time() >= deadline:
            log.error("IR device '%s' not found within %.0fs", device_name, timeout)
            raise SystemExit(1)
        log.debug("IR device '%s' not found, retrying in %.1fs...", device_name, poll_interval)
        await asyncio.sleep(poll_interval)


async def listen(device, mapper) -> None:
    """Read evdev events from device and dispatch scancodes to mapper.

    Pairs EV_MSC/MSC_SCAN (raw IR scancode) with subsequent EV_KEY (key state)
    and calls mapper.handle_scancode(scancode_hex, event_value).

    Args:
        device: evdev.InputDevice (or mock with async_read_loop()).
        mapper: CommandMapper instance with handle_scancode(str, int) method.

    Raises:
        SystemExit: If device disappears (OSError).
    """
    last_scancode: str | None = None
    log.info("Listening on %s (%s)", device.path, device.name)

    try:
        async for event in device.async_read_loop():
            if event.type == EV_MSC and event.code == MSC_SCAN:
                last_scancode = f"0x{event.value:06x}"
            elif event.type == EV_KEY:
                if last_scancode is not None:
                    await mapper.handle_scancode(last_scancode, event.value)
                    if event.value == 0:  # key-up resets scancode
                        last_scancode = None
                else:
                    log.warning(
                        "EV_KEY without preceding MSC_SCAN (keycode=%d, value=%d)",
                        event.code,
                        event.value,
                    )
    except OSError as e:
        log.error("IR device lost: %s", e)
        raise SystemExit(1) from e
