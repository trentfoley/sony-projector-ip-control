---
phase: 03-ir-listener-and-application
plan: 02
subsystem: cli-entry-point
tags: [argparse, asyncio, signal-handling, discover-mode, cli]

# Dependency graph
requires:
  - phase: 03-ir-listener-and-application
    provides: listener.py with find_ir_device() and listen() async event loop
  - phase: 02-command-mapper
    provides: CommandMapper.handle_scancode(scancode, event_value) API
  - phase: 01-foundation
    provides: Config dataclass, load_config(), ConfigError
provides:
  - __main__.py CLI entry point with argparse, async_main, discover mode, signal handling
  - projector-bridge console script and python -m projector_bridge invocation
  - _find_config() search path for config file resolution
  - 12 tests covering CLI, discover mode, config search, and graceful shutdown
affects: [04-wifi-bridge, 05-deployment, systemd-service]

# Tech tracking
tech-stack:
  added: []
  patterns: [argparse-cli, signal-based-shutdown, config-search-path, lazy-ecodes-import]

key-files:
  created:
    - src/projector_bridge/__main__.py
    - tests/test_main.py
  modified: []

key-decisions:
  - "Lazy import of evdev.ecodes in _discover_loop() with ImportError fallback -- ecodes unavailable on non-Linux, discover mode degrades to KEY_UNKNOWN(code) format"
  - "Platform guard for add_signal_handler with NotImplementedError catch -- Windows falls back to KeyboardInterrupt"

patterns-established:
  - "Config search path: --config flag > ./projector-bridge.yaml > /etc/projector-bridge/config.yaml"
  - "Signal shutdown: loop.add_signal_handler cancels main_task, finally block closes device"
  - "Lazy ecodes import: try/except ImportError for Linux-only evdev submodules"

requirements-completed: [DEV-01, DEV-04, DEV-03, IRC-01, IRC-02, IRC-03]

# Metrics
duration: 2min
completed: 2026-04-10
---

# Phase 3 Plan 02: CLI Entry Point Summary

**CLI entry point with argparse (--config/--discover/--log-level/--version), async discover mode printing scancodes, and SIGTERM/SIGINT graceful shutdown with device cleanup**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-10T02:46:37Z
- **Completed:** 2026-04-10T02:48:18Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created __main__.py with full CLI wiring: argparse flags, config file search path, async discover mode, bridge mode pipeline, and signal-based graceful shutdown
- Created 12 passing tests covering discover mode output/filtering, config resolution, CLI flag parsing, and device cleanup on CancelledError
- Full test suite passes (62 tests) with no regressions from prior plans

## Task Commits

Each task was committed atomically:

1. **Task 1: Create __main__.py with CLI, discover mode, signal handling, and pipeline wiring** - `724354f` (feat)
2. **Task 2: Create test_main.py covering DEV-01, DEV-04, and CLI parsing** - `655c408` (test)

## Files Created/Modified
- `src/projector_bridge/__main__.py` - CLI entry point with main(), async_main(), _discover_loop(), _find_config()
- `tests/test_main.py` - 12 tests across 4 test classes (TestDiscoverMode, TestFindConfig, TestCLIParsing, TestGracefulShutdown)

## Decisions Made
- Lazy import of evdev.ecodes inside _discover_loop() with ImportError fallback -- ecodes is Linux-only, and discover mode should degrade gracefully to KEY_UNKNOWN(code) format on other platforms
- Platform guard for loop.add_signal_handler with NotImplementedError catch -- Windows does not support UNIX signal handlers, falls back to KeyboardInterrupt via try/except in main()

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 3 is now complete: listener.py (Plan 01) + __main__.py (Plan 02) deliver the full IR-to-ADCP pipeline
- `projector-bridge` console script and `python -m projector_bridge` both invoke main()
- Discover mode ready for IR scancode mapping on actual hardware
- Bridge mode wires config -> CommandMapper -> listener -> ADCP send pipeline
- Phase 4 (WiFi bridge) and Phase 5 (deployment/systemd) can proceed independently

---
*Phase: 03-ir-listener-and-application*
*Completed: 2026-04-10*
