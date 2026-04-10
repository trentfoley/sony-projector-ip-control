# Phase 3: IR Listener and Application - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

evdev IR reception, discover mode, full pipeline wiring (IR → CommandMapper → ADCP), CLI entry point, and graceful shutdown. This phase delivers the working end-to-end flow: press a button on the Sony remote, the projector responds. Also provides `--discover` mode for mapping new remote buttons.

Requirements: IRC-01, IRC-02, IRC-03, DEV-01, DEV-03, DEV-04

</domain>

<decisions>
## Implementation Decisions

### Discover mode output
- **D-01:** Print scancode + kernel key name per line (e.g. `0x010 KEY_VOLUMEUP`). Gives both the config key and the kernel mapping at a glance.
- **D-02:** Key-down events only (`value=1`). No repeat events. One clean line per button press.

### CLI & entry point
- **D-03:** Both console script (`projector-bridge`) and module invocation (`python -m projector_bridge`), pointing to the same main function. Console script via `[project.scripts]` in pyproject.toml.
- **D-04:** CLI flags: `--config PATH`, `--discover`, `--log-level DEBUG|INFO|WARNING|ERROR`, `--version`.

### Device detection & recovery
- **D-05:** On startup, poll for IR device matching `gpio_ir_recv` every 2-3 seconds, up to 30 seconds. Fail with non-zero exit if not found. Handles slow device initialization after boot.
- **D-06:** If device disappears mid-run, exit cleanly with error log. Let systemd `Restart=always` (Phase 5) handle recovery. No in-process reconnect logic.

### Logging defaults
- **D-07:** Default log level is INFO. Logs each ADCP command sent and unknown scancodes. Overridable via `--log-level` flag.
- **D-08:** Plain text format to stdout/stderr (e.g. `2026-04-09 12:34:56 INFO [mapper] Sent ADCP: power_on`). JSON logging is v2 scope (REL-02). No custom log rotation — systemd journald handles it.

### Claude's Discretion
- Internal module structure (listener.py, main.py, __main__.py — whatever makes sense)
- Signal handler implementation details (asyncio signal handling approach)
- evdev device enumeration approach (iterate /dev/input/event* and match by name)
- Whether discover mode reuses the listener class or is a simpler standalone loop

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 & 2 code (integration points)
- `src/projector_bridge/config.py` — `Config`, `IRConfig`, `CommandMapping` dataclasses. IRConfig has `device_name` and `protocol` fields.
- `src/projector_bridge/mapper.py` — `CommandMapper.handle_scancode(scancode, event_value)` is the integration point. Phase 3 calls this per evdev event.
- `src/projector_bridge/adcp.py` — `send_command_with_retry()` called internally by mapper. Phase 3 does not call this directly.
- `src/projector_bridge/errors.py` — Typed exception hierarchy. Phase 3 may need `ConfigError` for CLI validation.

### Requirements
- `.planning/REQUIREMENTS.md` — IRC-01, IRC-02, IRC-03, DEV-01, DEV-03, DEV-04 define acceptance criteria.

### Research
- `.planning/research/FEATURES.md` — ADCP command format and protocol details.
- `.planning/research/PITFALLS.md` — Known risks for ADCP communication.

### External references (not in repo)
- [python-evdev docs](https://python-evdev.readthedocs.io/en/latest/tutorial.html) — `async_read_loop()` API for asyncio integration, device enumeration, input event constants.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CommandMapper` — fully implemented, tested, ready to wire into evdev loop
- `Config` / `load_config()` — YAML loader with validation, returns typed Config with IRConfig
- `IRConfig(device_name="gpio_ir_recv", protocol="sony")` — device name for evdev matching already configurable
- `send_command_with_retry()` — async ADCP send with retry, called internally by mapper

### Established Patterns
- Async throughout — `asyncio` event loop, all I/O is async
- `logging.getLogger(__name__)` — module-level logger pattern
- Typed exceptions with `ADCPError` hierarchy
- Dataclass-based config with sensible defaults

### Integration Points
- **evdev → CommandMapper:** Listener reads evdev events, extracts scancode (hex) and event value, calls `mapper.handle_scancode(scancode, event_value)`
- **Config → Listener:** `config.ir.device_name` tells the listener which `/dev/input/event*` device to open
- **CLI → everything:** `main()` parses args, loads config, creates mapper, starts listener or discover mode
- **Signal handlers → event loop:** SIGTERM/SIGINT trigger clean shutdown of the asyncio loop

</code_context>

<specifics>
## Specific Ideas

- evdev `async_read_loop()` integrates natively with asyncio — no threading or subprocess needed
- Scancodes from evdev events should be formatted as hex strings to match config mapping keys
- Discover mode bypasses the mapper entirely — just prints scancode + key name to stdout
- `pyproject.toml` needs `[project.scripts] projector-bridge = "projector_bridge.main:main"` (or equivalent)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-ir-listener-and-application*
*Context gathered: 2026-04-09*
