---
phase: 2
plan: 1
subsystem: command-mapper
tags: [mapper, debounce, rate-limit, adcp]
dependency_graph:
  requires: [config.py, adcp.py, errors.py]
  provides: [mapper.py]
  affects: [Phase 3 IR listener integration]
tech_stack:
  added: []
  patterns: [fire-and-forget asyncio.create_task, monotonic rate limiting]
key_files:
  created:
    - src/projector_bridge/mapper.py
  modified: []
decisions:
  - "D-01 through D-07 implemented as specified in 02-CONTEXT.md"
  - "Used asyncio.get_event_loop().time() for monotonic rate limiting"
  - "Fire-and-forget pattern with create_task prevents ADCP blocking event loop"
metrics:
  duration: 45s
  completed: "2026-04-10T01:48:45Z"
---

# Phase 2 Plan 1: CommandMapper Implementation Summary

CommandMapper class translating IR scancodes to ADCP commands with event-value-based repeat filtering, 100ms global rate limiting, and fire-and-forget async send.

## What Was Done

### Task 1: Create CommandMapper class
- **Commit:** 893b97f
- **Files:** `src/projector_bridge/mapper.py` (created, 70 lines)
- **Details:**
  - `CommandMapper.__init__(config: Config)` stores config and initializes `_last_send_time = 0.0`
  - `handle_scancode(scancode, event_value)` implements the full decision chain: key-up filter (D-02), mapping lookup with unknown-scancode logging (D-07), repeat gate (D-01), rate limit (D-03), fire-and-forget send
  - `_send(command, scancode)` wraps `send_command_with_retry` with `ADCPError` catch-and-log
  - Rate limiter uses `asyncio.get_event_loop().time()` (monotonic) with 100ms threshold
  - `asyncio.create_task()` ensures ADCP send does not block the event loop

## Verification Results

- `python -c "from projector_bridge.mapper import CommandMapper"` -- passed
- `ruff check src/projector_bridge/mapper.py` -- all checks passed
- Class has exactly one public method (`handle_scancode`) and one private method (`_send`)

## Deviations from Plan

None -- plan executed exactly as written.

## Self-Check: PASSED

- src/projector_bridge/mapper.py: FOUND
- Commit 893b97f: FOUND
