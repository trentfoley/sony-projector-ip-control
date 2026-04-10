# Phase 3: IR Listener and Application - Research

**Researched:** 2026-04-09
**Domain:** evdev IR reception, asyncio event loop, CLI entry point, graceful shutdown
**Confidence:** HIGH

## Summary

Phase 3 wires the complete IR-to-ADCP pipeline: an evdev-based IR listener reads key events from the kernel's gpio_ir_recv device, extracts scancodes, and feeds them to the already-implemented `CommandMapper`. The phase also delivers the CLI entry point (`projector-bridge` console script and `python -m projector_bridge`), `--discover` mode for mapping new buttons, and clean signal-based shutdown.

The existing codebase (Phase 1 and 2) provides all downstream components: `Config`/`load_config()` for YAML config, `CommandMapper.handle_scancode(scancode, event_value)` for IR-to-ADCP translation, and `send_command_with_retry()` for ADCP communication. Phase 3's job is the evdev listener, CLI argument parsing, logging setup, and the main asyncio loop that ties everything together.

**Primary recommendation:** Build three modules -- `listener.py` (evdev device discovery + async event loop), `__main__.py` (CLI parsing + entry point + signal handling), and update `__init__.py` with version. Use `evdev.list_devices()` to find the device by name, `async_read_loop()` for the event loop, and `loop.add_signal_handler()` for SIGTERM/SIGINT on Linux.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Discover mode prints scancode + kernel key name per line (e.g. `0x010 KEY_VOLUMEUP`). Both config key and kernel mapping at a glance.
- **D-02:** Key-down events only (`value=1`). No repeat events in discover mode. One clean line per button press.
- **D-03:** Both console script (`projector-bridge`) and module invocation (`python -m projector_bridge`), pointing to the same main function. Console script via `[project.scripts]` in pyproject.toml.
- **D-04:** CLI flags: `--config PATH`, `--discover`, `--log-level DEBUG|INFO|WARNING|ERROR`, `--version`.
- **D-05:** On startup, poll for IR device matching `gpio_ir_recv` every 2-3 seconds, up to 30 seconds. Fail with non-zero exit if not found. Handles slow device initialization after boot.
- **D-06:** If device disappears mid-run, exit cleanly with error log. Let systemd `Restart=always` handle recovery. No in-process reconnect logic.
- **D-07:** Default log level is INFO. Logs each ADCP command sent and unknown scancodes. Overridable via `--log-level` flag.
- **D-08:** Plain text format to stdout/stderr. JSON logging is v2 scope. No custom log rotation -- systemd journald handles it.

### Claude's Discretion
- Internal module structure (listener.py, main.py, __main__.py -- whatever makes sense)
- Signal handler implementation details (asyncio signal handling approach)
- evdev device enumeration approach (iterate /dev/input/event* and match by name)
- Whether discover mode reuses the listener class or is a simpler standalone loop

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| IRC-01 | Power on projector via remote | evdev listener feeds scancode to CommandMapper which sends `power "on"` ADCP command |
| IRC-02 | Power off projector via remote | Same pipeline with `power "off"` ADCP command |
| IRC-03 | Menu navigation via remote (up/down/left/right/enter/back) | Same pipeline with `key` ADCP commands; repeat=True mappings handle held buttons |
| DEV-01 | `--discover` mode prints raw scancodes without ADCP | Standalone evdev loop filtering EV_MSC MSC_SCAN + EV_KEY events, printing scancode + key name |
| DEV-03 | Auto-detect IR device by name, not hardcoded path | `evdev.list_devices()` + filter by `device.name == config.ir.device_name` |
| DEV-04 | Graceful shutdown on SIGTERM/SIGINT | `loop.add_signal_handler()` cancels main task, cleanup closes evdev device |
</phase_requirements>

## Standard Stack

### Core (already in pyproject.toml)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| evdev | >=1.9.0 | Read IR input events from kernel rc subsystem | Direct Python bindings to Linux input subsystem. `async_read_loop()` integrates natively with asyncio. No subprocess spawning | [VERIFIED: pyproject.toml] |
| PyYAML | >=6.0.2 | Parse config file | Already used by config.py | [VERIFIED: pyproject.toml] |

### Standard Library (no install needed)
| Module | Purpose | Notes |
|--------|---------|-------|
| asyncio | Event loop, signal handlers, task management | `asyncio.run()` for entry, `loop.add_signal_handler()` for SIGTERM/SIGINT |
| argparse | CLI argument parsing | `--config`, `--discover`, `--log-level`, `--version` flags |
| logging | Structured logging | `logging.basicConfig()` with configurable level |
| signal | Signal constants | `signal.SIGTERM`, `signal.SIGINT` for handler registration |
| importlib.metadata | Package version | `importlib.metadata.version("projector-bridge")` for `--version` flag |

**No new dependencies required.** Everything needed is either already in pyproject.toml or in the standard library.

## Architecture Patterns

### Recommended Module Structure
```
src/projector_bridge/
├── __init__.py          # Package docstring (exists)
├── __main__.py          # CLI entry point: argparse + asyncio.run(async_main())
├── listener.py          # IRListener class: device discovery + async event loop
├── config.py            # Config dataclasses + YAML loader (exists)
├── mapper.py            # CommandMapper (exists)
├── adcp.py              # ADCP TCP client (exists)
├── errors.py            # Exception hierarchy (exists)
└── mock_server.py       # Mock ADCP server for testing (exists)
```

### Pattern 1: evdev Device Discovery with Polling
**What:** Find the IR receiver device by name with retry polling [VERIFIED: CONTEXT.md D-05]
**When to use:** At daemon startup -- device may not be ready immediately after boot

```python
# Source: python-evdev docs + D-05 decision
import asyncio
import evdev

async def find_device(device_name: str, timeout: float = 30.0, poll_interval: float = 2.0) -> evdev.InputDevice:
    """Poll for an evdev device matching the given name."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        for path in evdev.list_devices():
            device = evdev.InputDevice(path)
            if device.name == device_name:
                return device
            device.close()
        await asyncio.sleep(poll_interval)
    raise RuntimeError(f"IR device '{device_name}' not found within {timeout}s")
```

### Pattern 2: Async Event Loop with evdev
**What:** Read IR events using `async_read_loop()` and dispatch to CommandMapper [VERIFIED: python-evdev GitHub docs]
**When to use:** Main daemon loop

```python
# Source: python-evdev tutorial + codebase mapper.py API
import evdev
from evdev import ecodes

async def listen(device: evdev.InputDevice, mapper: CommandMapper) -> None:
    """Read evdev events and dispatch to CommandMapper."""
    async for event in device.async_read_loop():
        if event.type == ecodes.EV_KEY:
            # event.code is the Linux keycode (int)
            # event.value: 0=up, 1=down, 2=repeat
            # Format scancode as hex string to match config mapping keys
            scancode = f"0x{event.code:06x}"
            await mapper.handle_scancode(scancode, event.value)
```

**Critical Note on Scancode Source:** The kernel IR subsystem generates two event types per button press:
1. `EV_MSC` (type 4) with `MSC_SCAN` (code 4) -- contains the raw IR scancode in `event.value`
2. `EV_KEY` (type 1) -- contains the mapped Linux keycode in `event.code`, press state in `event.value`

The config mappings use hex scancode strings (e.g., `"0x010015"`). These are the raw IR scancodes from `EV_MSC/MSC_SCAN`, NOT the Linux keycodes from `EV_KEY`. The listener must extract the scancode from the MSC_SCAN event and pair it with the key state from the EV_KEY event. [VERIFIED: kernel docs rc-protos.html, existing config format in conftest.py]

**Corrected pattern using MSC_SCAN for scancodes:**

```python
async def listen(device: evdev.InputDevice, mapper: CommandMapper) -> None:
    """Read evdev events and dispatch scancodes to CommandMapper."""
    last_scancode: str | None = None
    async for event in device.async_read_loop():
        if event.type == ecodes.EV_MSC and event.code == ecodes.MSC_SCAN:
            # Raw IR scancode arrives here; store for pairing with EV_KEY
            last_scancode = f"0x{event.value:06x}"
        elif event.type == ecodes.EV_KEY and last_scancode is not None:
            # event.value: 0=up, 1=down, 2=repeat
            await mapper.handle_scancode(last_scancode, event.value)
            if event.value == 0:  # key-up resets
                last_scancode = None
```

### Pattern 3: Discover Mode
**What:** Print scancode + kernel key name per button press [VERIFIED: CONTEXT.md D-01, D-02]
**When to use:** `--discover` flag

```python
async def discover(device: evdev.InputDevice) -> None:
    """Print scancodes and key names for discover mode."""
    last_scancode: int | None = None
    async for event in device.async_read_loop():
        if event.type == ecodes.EV_MSC and event.code == ecodes.MSC_SCAN:
            last_scancode = event.value
        elif event.type == ecodes.EV_KEY and event.value == 1:  # D-02: key-down only
            scancode_hex = f"0x{last_scancode:06x}" if last_scancode is not None else "unknown"
            key_name = ecodes.KEY.get(event.code, f"KEY_UNKNOWN({event.code})")
            if isinstance(key_name, list):
                key_name = key_name[0]  # Multiple names for same code
            print(f"{scancode_hex} {key_name}")
            last_scancode = None
```

### Pattern 4: Signal Handling for Graceful Shutdown
**What:** Register SIGTERM/SIGINT handlers that cancel the main task [VERIFIED: Python docs asyncio-eventloop]
**When to use:** Main entry point

```python
# Source: Python docs loop.add_signal_handler
import asyncio
import signal

async def async_main(args) -> None:
    loop = asyncio.get_running_loop()
    main_task = asyncio.current_task()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, main_task.cancel)

    try:
        device = await find_device(config.ir.device_name)
        try:
            await listen(device, mapper)
        finally:
            device.close()  # Release evdev resource
    except asyncio.CancelledError:
        log.info("Shutdown signal received, exiting cleanly")
```

**Platform note:** `loop.add_signal_handler()` is UNIX-only. This is fine -- the target is Raspberry Pi (Linux). Tests on Windows must mock the signal setup. [VERIFIED: Python docs, cpython issue #137863]

### Pattern 5: CLI Entry Point
**What:** argparse-based CLI with `--config`, `--discover`, `--log-level`, `--version` [VERIFIED: CONTEXT.md D-03, D-04]

```python
# Source: D-03, D-04 decisions
# In __main__.py
import argparse
import asyncio
import importlib.metadata
import logging

def main() -> None:
    parser = argparse.ArgumentParser(description="IR-to-ADCP bridge for Sony projectors")
    parser.add_argument("--config", type=str, default=None, help="Path to config file")
    parser.add_argument("--discover", action="store_true", help="Print raw scancodes")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default="INFO", help="Logging level")
    parser.add_argument("--version", action="version",
                        version=importlib.metadata.version("projector-bridge"))
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    asyncio.run(async_main(args))

if __name__ == "__main__":
    main()
```

### Anti-Patterns to Avoid
- **Hardcoded device paths:** Never use `/dev/input/event0` -- always discover by name [VERIFIED: PITFALLS.md Pitfall 9]
- **Threading for evdev:** `async_read_loop()` integrates natively with asyncio -- no threads needed [VERIFIED: python-evdev docs]
- **KeyboardInterrupt catching:** Use `loop.add_signal_handler()` instead -- it is cleaner and works with the asyncio event loop [VERIFIED: Python asyncio docs]
- **In-process reconnection:** Per D-06, if the device disappears, exit cleanly and let systemd restart [VERIFIED: CONTEXT.md D-06]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| IR event reading | Raw `/dev/input` read + struct.unpack | `evdev.InputDevice.async_read_loop()` | Handles event parsing, timestamps, and asyncio integration |
| Device discovery | Shell out to `find /dev/input` | `evdev.list_devices()` + name filter | Cross-checks device capabilities, handles permissions |
| Key name lookup | Hardcoded scancode-to-name table | `evdev.ecodes.KEY[code]` | Kernel-maintained mapping, always current |
| Signal handling | `signal.signal()` in async code | `loop.add_signal_handler()` | Thread-safe integration with asyncio event loop |
| Version string | Hardcoded `__version__` | `importlib.metadata.version()` | Single source of truth from pyproject.toml |

## Common Pitfalls

### Pitfall 1: Scancode vs Keycode Confusion
**What goes wrong:** Confusing evdev's `event.code` (Linux keycode) with the raw IR scancode from `MSC_SCAN`. The config mappings use raw IR scancodes (e.g., `0x010015`), not Linux keycodes (e.g., `KEY_POWER = 116`).
**Why it happens:** Both arrive as integers in evdev events but from different event types.
**How to avoid:** Extract scancodes from `EV_MSC`/`MSC_SCAN` events (type=4, code=4), not from `EV_KEY` events. The `event.value` field of MSC_SCAN contains the raw scancode.
**Warning signs:** All buttons produce the same response, or no mappings match. [VERIFIED: kernel docs, PITFALLS.md Pitfall 1]

### Pitfall 2: evdev Device Disappearance
**What goes wrong:** If the IR receiver is disconnected or the kernel module unloads, `async_read_loop()` raises `OSError` (errno 19: No such device).
**Why it happens:** The evdev device node is removed from `/dev/input/`.
**How to avoid:** Catch `OSError` in the event loop, log the error, and exit cleanly per D-06.
**Warning signs:** `OSError: [Errno 19] No such device` in logs. [ASSUMED]

### Pitfall 3: Multiple Names for Same Keycode
**What goes wrong:** `ecodes.KEY[code]` sometimes returns a list of names (e.g., `['KEY_COFFEE', 'KEY_SCREENLOCK']` for code 152) instead of a single string.
**Why it happens:** Some Linux keycodes have aliases.
**How to avoid:** Check if the return value is a list and use the first element.
**Warning signs:** TypeError in discover mode output formatting. [VERIFIED: python-evdev docs]

### Pitfall 4: Config File Search Path
**What goes wrong:** User runs `projector-bridge` without `--config` and it cannot find the config file.
**Why it happens:** No default search path is defined.
**How to avoid:** Define a search order: `--config` flag > `./projector-bridge.yaml` > `/etc/projector-bridge/config.yaml`. Log which config file was loaded.
**Warning signs:** `ConfigError: Config file not found` on first run. [ASSUMED]

### Pitfall 5: `loop.add_signal_handler` on Windows
**What goes wrong:** Tests fail on Windows dev machines because `add_signal_handler` is UNIX-only.
**Why it happens:** Windows asyncio event loop does not support POSIX signal handlers.
**How to avoid:** Guard signal handler setup with a platform check or try/except `NotImplementedError`. Tests should mock the signal setup.
**Warning signs:** `NotImplementedError` during test runs. [VERIFIED: Python docs, cpython issue #137863]

## Code Examples

### Complete Event Flow (MSC_SCAN to CommandMapper)
```python
# Source: Synthesized from python-evdev docs + codebase mapper.py
from evdev import InputDevice, ecodes
import logging

log = logging.getLogger(__name__)

async def event_loop(device: InputDevice, mapper) -> None:
    """Main event loop: reads evdev events and dispatches to mapper."""
    last_scancode: str | None = None
    log.info("Listening on %s (%s)", device.path, device.name)

    try:
        async for event in device.async_read_loop():
            if event.type == ecodes.EV_MSC and event.code == ecodes.MSC_SCAN:
                last_scancode = f"0x{event.value:06x}"
            elif event.type == ecodes.EV_KEY and last_scancode is not None:
                await mapper.handle_scancode(last_scancode, event.value)
                if event.value == 0:  # key-up
                    last_scancode = None
    except OSError as e:
        log.error("IR device lost: %s", e)
        raise SystemExit(1) from e
```

### Device Discovery with Polling
```python
# Source: D-05 decision + python-evdev list_devices API
async def find_ir_device(name: str, timeout: float = 30.0) -> InputDevice:
    """Find an evdev device by name, polling until found or timeout."""
    import evdev
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        for path in evdev.list_devices():
            dev = evdev.InputDevice(path)
            if dev.name == name:
                log.info("Found IR device: %s at %s", name, path)
                return dev
            dev.close()
        if asyncio.get_event_loop().time() >= deadline:
            raise SystemExit(f"IR device '{name}' not found within {timeout}s")
        log.debug("IR device '%s' not found, retrying...", name)
        await asyncio.sleep(2.0)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LIRC daemon (lircd) | Kernel rc subsystem + ir-keytable | Kernel 4.19+ (2018) | No userspace daemon needed for IR decoding |
| pigpio userspace decoding | gpio-ir kernel overlay | Kernel 4.19+ | Reliable interrupt-driven decoding, no timing jitter |
| `signal.signal()` for asyncio | `loop.add_signal_handler()` | Python 3.4+ | Thread-safe signal handling in asyncio |
| `pkg_resources.get_distribution` | `importlib.metadata.version()` | Python 3.8+ (PEP 566) | No setuptools runtime dependency |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `async_read_loop()` raises `OSError` when device disappears | Pitfall 2 | Need different exception handling for device loss |
| A2 | Default config search order (./projector-bridge.yaml then /etc/) | Pitfall 4 | Minor -- user can always pass --config |
| A3 | Scancode hex format from MSC_SCAN matches config mapping keys when formatted as `0x{value:06x}` | Architecture Pattern 2 | Critical -- if format differs, no mappings will match. Must be validated on hardware via discover mode |

## Open Questions

1. **Scancode hex format width**
   - What we know: Config uses `"0x010015"` (6 hex digits). Sony-12 uses 12 bits, Sony-15 uses 15 bits, Sony-20 uses 20 bits. The kernel packs these differently.
   - What's unclear: Whether `06x` zero-padding matches what the kernel actually outputs. The kernel may use variable-width hex.
   - Recommendation: Use discover mode on real hardware to verify. Format with `06x` padding and log the raw integer too at DEBUG level so mismatches are detectable. The format width should be a constant that is easy to change.

2. **Whether EV_MSC always precedes EV_KEY for IR events**
   - What we know: The standard kernel event sequence is MSC_SCAN, then EV_KEY, then EV_SYN. [CITED: kernel docs event-codes.txt]
   - What's unclear: Whether this ordering is guaranteed by the rc subsystem or just typical.
   - Recommendation: Handle the case where EV_KEY arrives without a preceding MSC_SCAN by using the keycode as a fallback. Log a warning.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.4 + pytest-asyncio >=1.3.0 |
| Config file | pyproject.toml (`asyncio_mode = "auto"`) |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IRC-01 | Power on via scancode -> ADCP | unit (mock evdev + ADCP) | `pytest tests/test_listener.py::test_power_on_scancode -x` | No -- Wave 0 |
| IRC-02 | Power off via scancode -> ADCP | unit (mock evdev + ADCP) | `pytest tests/test_listener.py::test_power_off_scancode -x` | No -- Wave 0 |
| IRC-03 | Menu nav scancodes -> ADCP | unit (mock evdev + ADCP) | `pytest tests/test_listener.py::test_nav_scancodes -x` | No -- Wave 0 |
| DEV-01 | Discover mode prints scancodes | unit (mock evdev, capture stdout) | `pytest tests/test_main.py::test_discover_mode -x` | No -- Wave 0 |
| DEV-03 | Auto-detect device by name | unit (mock evdev.list_devices) | `pytest tests/test_listener.py::test_device_discovery -x` | No -- Wave 0 |
| DEV-04 | Graceful shutdown on signal | unit (send signal, assert clean exit) | `pytest tests/test_main.py::test_graceful_shutdown -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_listener.py` -- covers IRC-01, IRC-02, IRC-03, DEV-03, device discovery + event loop
- [ ] `tests/test_main.py` -- covers DEV-01, DEV-04, CLI parsing, discover mode, signal handling
- [ ] Mock evdev fixtures in `tests/conftest.py` (extend existing) -- mock `InputDevice`, `list_devices()`, event objects

### Testing Strategy for evdev (Linux-only library)
Since evdev is Linux-only and development is on Windows, all tests must mock evdev objects completely:
- Mock `evdev.list_devices()` to return fake device paths
- Mock `evdev.InputDevice` with configurable `.name` attribute
- Mock `async_read_loop()` as an async generator yielding fake events
- Create a `FakeEvent` dataclass with `type`, `code`, `value` attributes
- Mock `evdev.ecodes` constants (EV_KEY, EV_MSC, MSC_SCAN, KEY dict)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A (ADCP auth handled in Phase 1) |
| V3 Session Management | No | N/A |
| V4 Access Control | Yes (minor) | evdev device requires `input` group membership |
| V5 Input Validation | Yes | Validate config file path exists; validate scancode format before mapper lookup |
| V6 Cryptography | No | N/A (SHA256 auth in Phase 1) |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed config path injection | Tampering | `Path.resolve()` + existence check before `open()` (already in config.py) |
| Runaway event loop (stuck async task) | Denial of Service | Signal handlers + `asyncio.CancelledError` propagation |
| Unclosed evdev file descriptor | Resource exhaustion | `finally:` block with `device.close()` |

## Sources

### Primary (HIGH confidence)
- [python-evdev GitHub docs (tutorial.rst)](https://github.com/gvalkov/python-evdev/blob/main/docs/tutorial.rst) -- async_read_loop, device enumeration, event structure
- [python-evdev GitHub docs (usage.rst)](https://github.com/gvalkov/python-evdev/blob/main/docs/usage.rst) -- InputDevice attributes, list_devices(), ecodes module
- [Linux Kernel RC Protocols](https://www.kernel.org/doc/html/latest/userspace-api/media/rc/rc-protos.html) -- Sony SIRC scancode bit layout
- [Linux Kernel event-codes.txt](https://www.kernel.org/doc/Documentation/input/event-codes.txt) -- EV_MSC/MSC_SCAN event semantics
- [Python asyncio event loop docs](https://docs.python.org/3/library/asyncio-eventloop.html) -- `add_signal_handler()` API
- Codebase: `src/projector_bridge/mapper.py` -- `CommandMapper.handle_scancode()` API
- Codebase: `src/projector_bridge/config.py` -- `Config`, `IRConfig` dataclasses
- Codebase: `tests/conftest.py` -- existing test fixtures and scancode format (`"0x010015"`)
- Codebase: `pyproject.toml` -- existing `[project.scripts]` entry point definition

### Secondary (MEDIUM confidence)
- [Raspberry Pi Forums: GPIO IR remote](https://forums.raspberrypi.com/viewtopic.php?t=205490) -- gpio_ir_recv device name, event sequence
- [LibreELEC IR Remotes wiki](https://wiki.libreelec.tv/configuration/ir-remotes) -- ir-keytable + evdev integration patterns
- [roguelynn.com: asyncio graceful shutdowns](https://roguelynn.com/words/asyncio-graceful-shutdowns/) -- signal handler patterns

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries verified in existing pyproject.toml, no new dependencies
- Architecture: HIGH -- evdev API well-documented, integration points clear from existing code
- Pitfalls: HIGH -- documented in project PITFALLS.md and verified against official kernel docs
- Scancode format: MEDIUM -- hex format width needs hardware validation via discover mode

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable domain, evdev API unlikely to change)
