"""CLI entry point for the IR-to-ADCP bridge daemon."""

import argparse
import asyncio
import importlib.metadata
import logging
import signal
import sys
from pathlib import Path

from projector_bridge.config import load_config
from projector_bridge.errors import ConfigError
from projector_bridge.listener import EV_KEY, EV_MSC, MSC_SCAN, find_ir_device, listen
from projector_bridge.mapper import CommandMapper

log = logging.getLogger(__name__)

# Default config search paths (first match wins)
_CONFIG_SEARCH_PATHS = [
    Path("projector-bridge.yaml"),
    Path("/etc/projector-bridge/config.yaml"),
]


def _find_config(cli_path: str | None) -> Path:
    """Resolve config file path from CLI flag or default search paths.

    Args:
        cli_path: Explicit --config value, or None.

    Returns:
        Resolved Path to the config file.

    Raises:
        ConfigError: If no config file found.
    """
    if cli_path is not None:
        p = Path(cli_path)
        if not p.exists():
            raise ConfigError(f"Config file not found: {p}")
        return p

    for p in _CONFIG_SEARCH_PATHS:
        if p.exists():
            log.info("Using config file: %s", p)
            return p

    raise ConfigError(
        "No config file found. Searched: "
        + ", ".join(str(p) for p in _CONFIG_SEARCH_PATHS)
        + ". Use --config PATH to specify."
    )


async def _discover_loop(device) -> None:
    """Print scancode + key name per button press (key-down only, per D-01 and D-02).

    Output format: '0xNNNNNN KEY_NAME' -- one line per button press.
    """
    try:
        # Lazy import ecodes for key name lookup
        from evdev import ecodes
    except ImportError:
        ecodes = None

    last_scancode: int | None = None
    async for event in device.async_read_loop():
        if event.type == EV_MSC and event.code == MSC_SCAN:
            last_scancode = event.value
        elif event.type == EV_KEY and event.value == 1:  # D-02: key-down only
            scancode_hex = f"0x{last_scancode:06x}" if last_scancode is not None else "unknown"
            # Look up kernel key name
            key_name = f"KEY_UNKNOWN({event.code})"
            if ecodes is not None:
                name = ecodes.KEY.get(event.code, key_name)
                if isinstance(name, list):
                    name = name[0]  # Multiple aliases for same code
                key_name = name
            print(f"{scancode_hex} {key_name}")
            last_scancode = None


async def async_main(args: argparse.Namespace) -> None:
    """Async entry point: discover mode or full bridge pipeline."""
    loop = asyncio.get_running_loop()
    main_task = asyncio.current_task()

    # Register signal handlers for graceful shutdown (UNIX-only)
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, main_task.cancel)
    except NotImplementedError:
        # Windows -- signal handlers not supported; KeyboardInterrupt still works
        pass

    if args.discover:
        # Discover mode: find device and print scancodes
        log.info("Starting discover mode -- press remote buttons to see scancodes")
        device = await find_ir_device("gpio_ir_recv")
        try:
            await _discover_loop(device)
        except asyncio.CancelledError:
            log.info("Discover mode stopped")
        finally:
            device.close()
            log.info("IR device closed")
    else:
        # Bridge mode: load config, create mapper, listen
        config_path = _find_config(args.config)
        config = load_config(config_path)
        log.info(
            "Loaded config: projector=%s:%d, %d mappings",
            config.projector.host,
            config.projector.port,
            len(config.mappings),
        )

        mapper = CommandMapper(config)
        device = await find_ir_device(config.ir.device_name)
        try:
            await listen(device, mapper)
        except asyncio.CancelledError:
            log.info("Shutdown signal received, exiting cleanly")
        finally:
            device.close()
            log.info("IR device closed")


def main() -> None:
    """Synchronous entry point for console_scripts and python -m invocation."""
    parser = argparse.ArgumentParser(
        prog="projector-bridge",
        description="IR-to-ADCP bridge for Sony projectors",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to YAML config file",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Print raw IR scancodes without sending ADCP commands",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=importlib.metadata.version("projector-bridge"),
    )
    args = parser.parse_args()

    # D-07, D-08: plain text format to stderr, default INFO
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stderr,
    )

    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        pass  # Clean exit on Ctrl+C (Windows fallback)


if __name__ == "__main__":
    main()
