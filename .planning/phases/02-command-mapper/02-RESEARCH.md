# Phase 2: Command Mapper — Research

**Researched:** 2026-04-10
**Phase:** 02-command-mapper
**Requirements:** MAP-02, MAP-03, MAP-04, MAP-05

## Executive Summary

Phase 2 implements a `CommandMapper` class that sits between IR input events (Phase 3) and the ADCP client (Phase 1). It translates scancodes into ADCP commands with debounce and rate limiting. The domain is well-bounded: all integration points exist from Phase 1, user decisions are locked, and the implementation is pure async Python with no external dependencies beyond what Phase 1 already provides.

## Integration Points (Phase 1 Codebase)

### Config Dataclasses (`src/projector_bridge/config.py`)

```python
@dataclass
class CommandMapping:
    command: str          # ADCP command string, e.g. 'power "on"'
    repeat: bool = False  # Whether held-button repeats should fire
    description: str = "" # Human-readable label

@dataclass
class Config:
    projector: ProjectorConfig
    mappings: dict[str, CommandMapping]  # scancode (hex str) -> mapping
    ir: IRConfig
```

**Key observations:**
- `Config.mappings` is a `dict[str, CommandMapping]` — O(1) lookup by scancode string key
- Scancode keys are hex strings (e.g., `"0x010015"`) as defined in the YAML config
- `CommandMapping.repeat` is the boolean the mapper uses to decide whether `event_value=2` should fire
- `ProjectorConfig` contains all connection parameters needed by `send_command_with_retry()`

### ADCP Client (`src/projector_bridge/adcp.py`)

```python
async def send_command_with_retry(config: ProjectorConfig, command: str) -> str:
```

**Key observations:**
- Takes `ProjectorConfig` (not full `Config`) and a command string
- Returns parsed response string ("ok", unquoted query value)
- Raises `ConnectionError` for transient failures (retried internally)
- Raises `AuthError`, `CommandError`, `CommandValueError`, `InactiveError` for non-transient errors (propagated immediately)
- Open-per-command model: each call opens a new TCP connection, authenticates, sends, closes
- The function is async and non-blocking

### Error Hierarchy (`src/projector_bridge/errors.py`)

```
ADCPError (base)
├── AuthError         (err_auth)
├── CommandError      (err_cmd)
├── CommandValueError (err_val)
├── InactiveError     (err_inactive)
└── ConnectionError   (connect/read timeout, refused)

ConfigError (separate hierarchy)
```

The mapper should catch `ADCPError` (all ADCP failures) for logging but not re-raise — the mapper is fire-and-forget from Phase 3's perspective.

## evdev Event Values

The Linux input subsystem delivers key events with three possible values:

| Value | Meaning | Mapper Action |
|-------|---------|---------------|
| 0 | Key up (released) | Always ignore (D-02) |
| 1 | Key down (pressed) | Fire command for all mappings (D-01) |
| 2 | Key repeat (held) | Fire only if `CommandMapping.repeat=True` (D-01) |

These are constants in the `evdev` module (`ecodes.EV_KEY` event type), but the mapper only receives the integer value — no evdev dependency needed in the mapper module itself.

## Rate Limiter Design

Per user decision D-03:
- Global 100ms minimum between ADCP sends
- Single `last_send_time` timestamp (monotonic clock)
- Lossy: if `now - last_send_time < 100ms`, silently drop the command
- No queue, no delay, no per-command rate tracking

**Implementation detail:** Use `asyncio.get_event_loop().time()` (monotonic) rather than `time.time()` (wall clock) to avoid issues with NTP corrections. The event loop's monotonic clock is the standard for asyncio timing.

**Edge case:** The first command ever sent should always fire (initialize `last_send_time` to 0 or a sufficiently old value).

## Async Concurrency Considerations

The mapper's `handle_scancode()` will be called from Phase 3's evdev async loop. Key considerations:

1. **`send_command_with_retry()` is async and takes 30-100ms+** (TCP connect + auth + send + close). The mapper should `asyncio.create_task()` the send to avoid blocking the evdev event loop while the TCP round-trip completes.

2. **Rate limiter check must happen synchronously** (before the task spawn) so that rapid events are dropped at the decision point, not after spawning concurrent sends.

3. **No serialization lock needed in the mapper itself.** The rate limiter's lossy drop ensures only one command fires per 100ms window. If two commands somehow pass the check simultaneously (theoretically possible with event loop scheduling), the projector handles concurrent TCP connections — this is an acceptable edge case given the 100ms window.

4. **Fire-and-forget pattern:** The spawned task should catch all exceptions and log them. The mapper never propagates ADCP errors upward to the evdev listener.

## Test Patterns (Phase 1 Reference)

From `tests/test_adcp.py` and `tests/conftest.py`:
- `asyncio_mode = "auto"` in pyproject.toml — all async tests run without decorators
- Inline TCP mock servers via `asyncio.start_server()` for integration tests
- `_make_config()` helper for building test configs
- `pytest.mark.parametrize` for error type testing
- No external mock libraries — just standard `unittest.mock` where needed

For the mapper tests, the primary mock target is `send_command_with_retry`. Use `unittest.mock.AsyncMock` to mock it as an async callable.

## File Placement

Following Phase 1 patterns:
- Source: `src/projector_bridge/mapper.py`
- Tests: `tests/test_mapper.py`
- Module follows the `log = logging.getLogger(__name__)` pattern established in `adcp.py`

## Validation Architecture

### Automated Test Strategy

| Requirement | Test Type | What to Verify |
|-------------|-----------|----------------|
| MAP-02 | Unit | `event_value=1` fires, `event_value=2` does NOT fire when `repeat=False` |
| MAP-03 | Unit | `event_value=2` fires when `repeat=True`, rate limit enforced at 100ms |
| MAP-04 | Unit | Unknown scancode logs at INFO, no ADCP send attempted |
| MAP-05 | Unit | Two rapid sends within 100ms — second is dropped |

All tests mock `send_command_with_retry` via `AsyncMock`. No TCP servers needed for mapper unit tests.

### Test commands
- Quick: `python -m pytest tests/test_mapper.py -x -q`
- Full: `python -m pytest tests/ -x -q`

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `create_task()` exceptions silently lost | Missed errors in logs | Add `task.add_done_callback()` that logs unhandled exceptions |
| Event loop time resolution on Pi | Rate limiter may be imprecise | 100ms is well above timer resolution (~1ms). Not a real concern. |
| Concurrent `handle_scancode` calls | Race on `last_send_time` | Single-threaded asyncio — no actual race. Check-then-send is atomic within a synchronous code block. |

## Sources

- Phase 1 source: `src/projector_bridge/config.py`, `adcp.py`, `errors.py`
- Phase 1 tests: `tests/test_adcp.py`, `tests/conftest.py`
- CONTEXT.md decisions D-01 through D-07
- Pitfall 4 (IR repeat flooding) and Pitfall 8 (connection serialization) from `.planning/research/PITFALLS.md`
- Python asyncio docs: `create_task()`, `get_event_loop().time()`
- evdev docs: event value constants (0=up, 1=down, 2=repeat)
