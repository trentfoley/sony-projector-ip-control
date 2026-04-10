---
phase: 2
plan: 2
subsystem: command-mapper
tags: [testing, unit-tests, mapper]
dependency_graph:
  requires: [02-01]
  provides: [test-coverage-mapper]
  affects: []
tech_stack:
  added: []
  patterns: [async-mock-patching, rate-limit-time-manipulation]
key_files:
  created:
    - tests/test_mapper.py
  modified: []
decisions:
  - Used _last_send_time manipulation for rate limit tests instead of real sleeps
  - Used asyncio.sleep(0) drain pattern to flush create_task callbacks
metrics:
  duration: 87s
  completed: 2026-04-09
---

# Phase 2 Plan 2: CommandMapper Unit Tests Summary

**9 async unit tests covering all four mapper requirements with mocked ADCP send layer**

## What Was Done

### Task 1: Create test_mapper.py with full coverage

Created `tests/test_mapper.py` with 9 test functions covering all requirements:

| Test | Requirement | What it verifies |
|------|------------|-----------------|
| test_keydown_fires_command | MAP-02 | event_value=1 with mapped scancode calls send exactly once |
| test_keyup_ignored | D-02 | event_value=0 never triggers send |
| test_non_repeat_ignores_hold | MAP-02 | event_value=2 with repeat=False does not send |
| test_repeat_fires_on_hold | MAP-03 | event_value=2 with repeat=True does send |
| test_unknown_scancode_logged | MAP-04 | Unmapped scancode logs INFO with hex value, no send |
| test_rate_limit_drops_rapid_sends | MAP-05 | Second call within 100ms is dropped |
| test_rate_limit_allows_after_interval | MAP-05 | Calls with >100ms gap both fire |
| test_adcp_error_logged_not_raised | Error handling | ADCPError caught and logged, not propagated |
| test_first_command_always_fires | MAP-05 edge | First command always fires (last_send_time=0) |

## Test Results

- `tests/test_mapper.py`: 9/9 passed
- Full suite (`tests/`): 39/39 passed (no regressions)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 027866f | 9 CommandMapper unit tests covering all requirements |

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED
