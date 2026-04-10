---
phase: 03-ir-listener-and-application
plan: 01
subsystem: ir-listener
tags: [evdev, asyncio, ir-receiver, gpio, input-events]

# Dependency graph
requires:
  - phase: 02-command-mapper
    provides: CommandMapper.handle_scancode(scancode, event_value) API
provides:
  - listener.py with find_ir_device() polling discovery and listen() async event loop
  - evdev mock fixtures (FakeEvent, fake_ir_device, make_events) in conftest.py
  - 11 listener tests covering IRC-01, IRC-02, IRC-03, DEV-03
affects: [03-02, main-entry-point, discover-mode]

# Tech tracking
tech-stack:
  added: []
  patterns: [lazy-evdev-import, msc-scan-ev-key-pairing, sys-modules-mock-for-linux-only-libs]

key-files:
  created:
    - src/projector_bridge/listener.py
    - tests/test_listener.py
  modified:
    - tests/conftest.py

key-decisions:
  - "Used sys.modules patching instead of patch(create=True) for evdev mocking -- lazy import inside function body requires injecting into sys.modules before the import statement executes"
  - "Scancode extracted from EV_MSC/MSC_SCAN events (not EV_KEY.code) -- raw IR scancodes match config mapping keys"

patterns-established:
  - "Lazy evdev import: import inside find_ir_device() to avoid ImportError on non-Linux dev machines"
  - "MSC_SCAN + EV_KEY pairing: store last scancode from MSC_SCAN, dispatch on EV_KEY, reset on key-up"
  - "sys.modules mock pattern: patch.dict(sys.modules, {'evdev': mock}) for testing Linux-only libraries on Windows"

requirements-completed: [IRC-01, IRC-02, IRC-03, DEV-03]

# Metrics
duration: 4min
completed: 2026-04-10
---

# Phase 3 Plan 01: IR Listener Summary

**Async evdev listener with MSC_SCAN scancode extraction, polling device discovery, and 11 tests covering power/nav/discovery requirements**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-10T02:40:47Z
- **Completed:** 2026-04-10T02:44:24Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created listener.py with find_ir_device() (30s timeout, 2s polling, SystemExit on failure) and listen() (MSC_SCAN/EV_KEY pairing, mapper dispatch, OSError handling)
- Extended conftest.py with FakeEvent dataclass, fake_ir_device and make_events fixtures without breaking existing fixtures
- Created 11 passing tests covering all plan requirements (IRC-01, IRC-02, IRC-03, DEV-03) plus device loss, fd leak prevention, and edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1: Create evdev mock fixtures and IR listener module** - `ede2695` (feat)
2. **Task 2: Create listener tests** - `080039f` (test)

## Files Created/Modified
- `src/projector_bridge/listener.py` - IR listener with device discovery and async event loop
- `tests/test_listener.py` - 11 tests for listener module (7 listen tests, 4 discovery tests)
- `tests/conftest.py` - Added FakeEvent, fake_ir_device, make_events fixtures

## Decisions Made
- Used `sys.modules` patching for evdev mock instead of `patch(create=True)` -- the lazy `import evdev` inside `find_ir_device()` does a real import lookup that `create=True` cannot intercept; `patch.dict(sys.modules)` injects the mock before the import statement executes
- Kept evdev constants (EV_KEY=1, EV_MSC=4, MSC_SCAN=4) as module-level constants in listener.py to avoid importing evdev at module load time

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed evdev mock strategy for find_ir_device tests**
- **Found during:** Task 2 (listener tests)
- **Issue:** Plan used `patch("projector_bridge.listener.evdev", create=True)` but this does not intercept the `import evdev` statement inside `find_ir_device()` -- Python's import machinery looks up sys.modules, not module attributes
- **Fix:** Changed to `patch.dict(sys.modules, {"evdev": mock_evdev})` which injects the mock before the import resolves
- **Files modified:** tests/test_listener.py
- **Verification:** All 11 tests pass
- **Committed in:** 080039f (Task 2 commit)

**2. [Rule 3 - Blocking] Installed package in dev mode**
- **Found during:** Task 2 (before running tests)
- **Issue:** `projector_bridge` module not importable -- package not installed in venv
- **Fix:** Ran `pip install -e ".[dev]" --no-deps` (--no-deps because evdev cannot build on Windows)
- **Files modified:** None (venv only)
- **Verification:** All 50 tests pass

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes necessary for tests to run on Windows dev machine. No scope creep.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- listener.py is ready for integration with the CLI entry point (__main__.py) in Plan 03-02
- find_ir_device() accepts device_name from config.ir.device_name
- listen() accepts any mapper with async handle_scancode(str, int) method
- Discover mode (Plan 03-02) can reuse the same MSC_SCAN/EV_KEY pairing pattern

---
*Phase: 03-ir-listener-and-application*
*Completed: 2026-04-10*
