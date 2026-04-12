# Phase 2: Command Mapper - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Scancode-to-ADCP translation layer with debounce, repeat handling, and rate limiting. The command mapper sits between IR input events (Phase 3) and the ADCP client (Phase 1), deciding whether each scancode event should fire an ADCP command and enforcing a global send rate. This phase delivers a testable `CommandMapper` class that Phase 3 wires into the evdev event loop.

Requirements: MAP-02, MAP-03, MAP-04, MAP-05

</domain>

<decisions>
## Implementation Decisions

### Debounce logic
- **D-01:** Use evdev event value directly — `value=1` (key down) fires for all commands, `value=2` (repeat) fires only when `CommandMapping.repeat=True`. No time-window debounce, no timers. Kernel handles repeat rate (~250ms default).
- **D-02:** `value=0` (key up) is always ignored — no action on button release.

### Rate limiter design
- **D-03:** Global 100ms minimum between ADCP sends, enforced by a single `last_send_time` timestamp. If `now - last_send_time < 100ms`, the command is silently dropped (lossy). No queue, no delay.
- **D-04:** Kernel repeat rate (~250ms) means held-button repeats won't normally hit the rate limiter. This is an edge-case safety net, not the primary flow control.

### Mapper architecture
- **D-05:** Stateful `CommandMapper` class. Takes `Config` at init, exposes `async handle_scancode(scancode: str, event_value: int)` as the single integration point. Holds mapping table, projector config, and last-send timestamp internally.
- **D-06:** `handle_scancode()` is the only public method Phase 3 needs to call — one method per evdev event. The mapper owns the full decision chain: lookup → repeat check → rate limit → send.

### Unknown scancode handling
- **D-07:** Log each unknown scancode at INFO with its hex value. No deduplication, no counting, no session summaries. Discover mode (Phase 3) is the proper tool for systematic button mapping.

### Claude's Discretion
- Internal method decomposition within CommandMapper (private helpers for lookup, rate check, etc.)
- Logging format for successful sends, rate-limited drops, and unknown scancodes
- Whether `handle_scancode` returns a result/status or is fire-and-forget
- Test structure and mock strategy for unit testing the mapper without a real ADCP connection

</decisions>

<specifics>
## Specific Ideas

- The mapper must be fully testable without hardware — mock the ADCP `send_command_with_retry()` call
- `CommandMapping` dataclass already has `repeat: bool` in config.py — mapper reads this directly
- Scancodes are hex strings (dict keys in config mappings) — mapper receives string scancodes, not raw ints
- Phase 3 will call `handle_scancode()` from an async evdev event loop — method must be async and non-blocking

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 code (integration points)
- `src/projector_bridge/config.py` — `Config`, `ProjectorConfig`, `CommandMapping` dataclasses. Mapper consumes these directly.
- `src/projector_bridge/adcp.py` — `send_command_with_retry(config, command)` is the downstream ADCP call target.
- `src/projector_bridge/errors.py` — Typed ADCP exceptions. Mapper should handle/log these appropriately.

### Requirements
- `.planning/REQUIREMENTS.md` — MAP-02 through MAP-05 define the acceptance criteria for this phase.

### Research
- `.planning/research/FEATURES.md` — ADCP command format and error codes relevant to what the mapper sends.
- `.planning/research/PITFALLS.md` — Known risks for ADCP communication that affect mapper error handling.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CommandMapping(command, repeat, description)` — already defined in config.py, has the `repeat` flag the mapper needs
- `send_command_with_retry(config, command)` — async ADCP send with retry, the mapper's downstream call
- `Config.mappings: dict[str, CommandMapping]` — scancode-keyed O(1) lookup table, ready to use

### Established Patterns
- Async throughout — `asyncio` is the concurrency model, all I/O is async
- Typed exceptions — `ADCPError` hierarchy for protocol errors, `ConfigError` for config issues
- `logging.getLogger(__name__)` — module-level logger pattern established in adcp.py

### Integration Points
- **Upstream (Phase 3):** IR listener will call `mapper.handle_scancode(scancode, event_value)` per evdev event
- **Downstream (Phase 1):** Mapper calls `send_command_with_retry(config.projector, mapping.command)`
- **Config:** Mapper receives `Config` instance at init, reads `config.mappings` and `config.projector`

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-command-mapper*
*Context gathered: 2026-04-10*
