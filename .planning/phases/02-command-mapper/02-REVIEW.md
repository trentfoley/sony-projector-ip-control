---
phase: 02-command-mapper
reviewed: 2026-04-09T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - src/projector_bridge/mapper.py
  - tests/test_mapper.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-04-09
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

The CommandMapper implementation is clean, well-structured, and follows the project conventions described in CLAUDE.md. The async pattern, rate limiting, repeat filtering, and error handling are all sound. The test suite covers the key behavioral contracts (key-up ignore, repeat filtering, rate limiting, error logging) with clear test names referencing design decisions.

Two warnings relate to task lifecycle safety and a deprecated asyncio API. One informational item about an unhandled exception path in fire-and-forget tasks.

## Warnings

### WR-01: Fire-and-forget task may be garbage collected before completion

**File:** `src/projector_bridge/mapper.py:62`
**Issue:** `asyncio.create_task()` returns a Task object that is immediately discarded. Python's asyncio documentation warns that the event loop only holds a weak reference to tasks. If no strong reference exists, the task may be garbage collected mid-execution, silently cancelling the ADCP send. This is especially relevant on CPython where GC timing is non-deterministic under memory pressure.
**Fix:** Store task references in a set and use a done callback to discard them:
```python
class CommandMapper:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._last_send_time: float = 0.0
        self._pending_tasks: set[asyncio.Task] = set()

    async def handle_scancode(self, scancode: str, event_value: int) -> None:
        # ... existing logic ...
        task = asyncio.create_task(self._send(mapping.command, scancode))
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)
```

### WR-02: Deprecated `asyncio.get_event_loop()` usage

**File:** `src/projector_bridge/mapper.py:50`
**Issue:** `asyncio.get_event_loop()` has been deprecated since Python 3.10 and emits a DeprecationWarning when no running loop exists. While it works correctly inside an `async` method (there is always a running loop), using the deprecated API is a maintenance risk -- future Python versions may remove it. The project targets Python 3.11+.
**Fix:**
```python
now = asyncio.get_running_loop().time()
```
Also update `tests/test_mapper.py:122` which uses the same pattern:
```python
mapper._last_send_time = asyncio.get_running_loop().time()
```
And line 143:
```python
mapper._last_send_time = asyncio.get_running_loop().time() - 0.2
```

## Info

### IN-01: Unexpected exceptions in fire-and-forget task are silently lost

**File:** `src/projector_bridge/mapper.py:64-70`
**Issue:** The `_send` method catches `ADCPError` but not broader exceptions (e.g., `TypeError` from unexpected data, or `AttributeError` from config issues). Any non-`ADCPError` exception raised inside the `create_task` coroutine will produce a "Task exception was never retrieved" warning in logs but otherwise be silently lost. For a daemon that runs unattended, this could mask bugs.
**Fix:** Add a catch-all for `Exception` with error logging:
```python
async def _send(self, command: str, scancode: str) -> None:
    try:
        await send_command_with_retry(self._config.projector, command)
        log.debug("Sent ADCP command: %s (scancode: %s)", command, scancode)
    except ADCPError as e:
        log.error("ADCP error for scancode %s: %s", scancode, e)
    except Exception:
        log.exception("Unexpected error sending command for scancode %s", scancode)
```

---

_Reviewed: 2026-04-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
