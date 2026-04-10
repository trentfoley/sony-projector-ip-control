---
phase: 03-ir-listener-and-application
verified: 2026-04-09T23:00:00Z
status: human_needed
score: 5/5
overrides_applied: 0
human_verification:
  - test: "Press power button on Sony remote and verify projector powers on"
    expected: "Projector powers on within a few seconds of button press"
    why_human: "Requires physical hardware (remote, TSOP38238 sensor, projector on network)"
  - test: "Press menu navigation buttons (up/down/left/right/enter/back) on remote"
    expected: "Projector OSD responds to navigation commands"
    why_human: "Requires physical hardware and visual confirmation of projector menu response"
  - test: "Run `python -m projector_bridge --discover`, press buttons, see scancodes"
    expected: "Each button press prints one line: 0xNNNNNN KEY_NAME"
    why_human: "Requires physical IR sensor and remote to produce real evdev events"
  - test: "Send SIGTERM to running daemon and verify clean shutdown"
    expected: "Process exits without error, no orphaned TCP connections"
    why_human: "Requires running daemon on RPi with real device to verify resource cleanup"
---

# Phase 3: IR Listener and Application Verification Report

**Phase Goal:** User can press buttons on the Sony remote and the projector responds, with discover mode available for mapping new buttons
**Verified:** 2026-04-09T23:00:00Z
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Pressing the power button on the Sony remote powers the projector on or off | VERIFIED | listener.py dispatches MSC_SCAN scancodes to mapper.handle_scancode(); test_power_on_scancode and test_power_off_scancode confirm 0x010015 dispatched with event_value=1. __main__.py wires listener -> CommandMapper -> ADCP send pipeline in bridge mode. |
| 2 | Pressing menu navigation buttons on the remote navigates projector menus | VERIFIED | test_nav_scancodes_key_down_and_repeat confirms 0x010074 dispatched for key-down (value=1) and repeat (value=2). listen() forwards all EV_KEY events with preceding MSC_SCAN to mapper. |
| 3 | Running with --discover prints raw scancodes to stdout without sending ADCP commands | VERIFIED | _discover_loop() prints "0xNNNNNN KEY_NAME" format, only on key-down (value=1). test_discover_prints_scancode_and_keyname confirms output contains scancode. test_discover_ignores_repeat_events and test_discover_ignores_key_up confirm filtering. No CommandMapper instantiation in discover path. |
| 4 | The IR input device is found automatically by name (gpio_ir_recv) regardless of /dev/input path | VERIFIED | find_ir_device() iterates evdev.list_devices(), matches by device.name, not path. test_device_found_immediately, test_device_found_on_retry, and test_non_matching_devices_closed confirm behavior. |
| 5 | Sending SIGTERM or SIGINT to the daemon shuts it down cleanly, releasing TCP and evdev resources | VERIFIED | async_main() registers loop.add_signal_handler(sig, main_task.cancel) for SIGTERM/SIGINT. CancelledError caught in try/except, device.close() called in finally block for both discover and bridge modes. test_cancelled_error_closes_device and test_bridge_mode_cancelled_closes_device confirm device.close() is called. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/projector_bridge/listener.py` | IRListener with device discovery and async event loop | VERIFIED | 80 lines. Contains find_ir_device() with 30s timeout, 2s polling, SystemExit on failure. Contains listen() with MSC_SCAN/EV_KEY pairing, mapper.handle_scancode() dispatch, OSError -> SystemExit. |
| `src/projector_bridge/__main__.py` | CLI entry point with argparse, async_main, discover mode, signal handling | VERIFIED | 173 lines. Contains main() with --config/--discover/--log-level/--version, async_main() with signal handlers, _discover_loop() with scancode printing, _find_config() with search path. |
| `tests/test_listener.py` | IR listener tests | VERIFIED | 205 lines. 11 tests across TestListen (7) and TestFindIRDevice (4). Covers IRC-01, IRC-02, IRC-03, DEV-03, device disappearance, edge cases. |
| `tests/test_main.py` | CLI entry point tests | VERIFIED | 183 lines. 12 tests across TestDiscoverMode (3), TestFindConfig (4), TestCLIParsing (3), TestGracefulShutdown (2). Covers DEV-01, DEV-04. |
| `tests/conftest.py` | Shared evdev mock fixtures | VERIFIED | Contains FakeEvent dataclass, EV_KEY/EV_MSC/MSC_SCAN constants, fake_ir_device and make_events fixtures. Existing tmp_config and sample_config_yaml fixtures preserved. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `__main__.py` | `listener.py` | `find_ir_device()` and `listen()` | WIRED | Line 13: `from projector_bridge.listener import ... find_ir_device, listen`. Used in async_main() at lines 99, 101, 119, 121. |
| `__main__.py` | `config.py` | `load_config()` | WIRED | Line 11: `from projector_bridge.config import load_config`. Used at line 110. |
| `__main__.py` | `mapper.py` | `CommandMapper(config)` | WIRED | Line 14: `from projector_bridge.mapper import CommandMapper`. Used at line 118. |
| `listener.py` | `mapper.py` | `mapper.handle_scancode(scancode, event_value)` | WIRED | Line 68: `await mapper.handle_scancode(last_scancode, event.value)`. Mapper passed as parameter to listen(). |
| `listener.py` | `evdev` | `async_read_loop()` and `list_devices()` | WIRED | Line 28: `import evdev` (lazy). Lines 33-34: `evdev.list_devices()`, `evdev.InputDevice()`. Line 63: `device.async_read_loop()`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| listener.py | `event` (from async_read_loop) | evdev kernel device | Yes -- kernel gpio-ir delivers real IR scancodes | FLOWING |
| listener.py | `last_scancode` | Extracted from EV_MSC/MSC_SCAN event.value | Yes -- formatted as hex string, passed to mapper | FLOWING |
| __main__.py (bridge) | `config` | load_config(config_path) from YAML file | Yes -- real file parsed by config.py | FLOWING |
| __main__.py (discover) | scancode output | evdev events via _discover_loop | Yes -- prints to stdout | FLOWING |

### Behavioral Spot-Checks

Step 7b: SKIPPED (requires Linux evdev subsystem and physical IR hardware -- not runnable on Windows dev machine)

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| IRC-01 | 03-01 | Power-on scancode dispatches to CommandMapper | SATISFIED | test_power_on_scancode: MSC_SCAN(0x010015) + EV_KEY(value=1) -> handle_scancode("0x010015", 1) |
| IRC-02 | 03-01 | Power-off scancode dispatches to CommandMapper | SATISFIED | test_power_off_scancode: Same button (0x010015) dispatched, mapper determines on/off action |
| IRC-03 | 03-01 | Menu navigation scancodes dispatch to CommandMapper | SATISFIED | test_nav_scancodes_key_down_and_repeat: 0x010074 dispatched for key-down and repeat |
| DEV-01 | 03-02 | Discover mode prints scancode + key name per button press | SATISFIED | test_discover_prints_scancode_and_keyname: output contains "0x010015" in correct format |
| DEV-03 | 03-01, 03-02 | IR device found by name, polling with timeout | SATISFIED | test_device_found_immediately, test_device_found_on_retry, test_device_not_found_timeout |
| DEV-04 | 03-02 | SIGTERM/SIGINT causes clean shutdown with device.close() | SATISFIED | test_cancelled_error_closes_device and test_bridge_mode_cancelled_closes_device confirm device.close() called |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | -- | -- | -- | No anti-patterns detected |

No TODOs, FIXMEs, placeholders, empty implementations, or stub patterns found in any phase artifacts.

### Human Verification Required

### 1. End-to-End IR Power Control

**Test:** Press power button on Sony remote with daemon running on RPi
**Expected:** Projector powers on/off within a few seconds
**Why human:** Requires physical hardware stack: Sony remote -> TSOP38238 sensor -> gpio_ir_recv -> daemon -> ADCP TCP -> projector

### 2. Menu Navigation via Remote

**Test:** Press up/down/left/right/enter/back on remote while in projector menu
**Expected:** Projector OSD responds to each navigation command
**Why human:** Requires visual confirmation of projector menu response to IR commands

### 3. Discover Mode on Real Hardware

**Test:** Run `python -m projector_bridge --discover` on RPi, press remote buttons
**Expected:** Each button press prints one line: `0xNNNNNN KEY_NAME` to stdout
**Why human:** Requires physical IR sensor producing real kernel input events

### 4. Signal-Based Shutdown on RPi

**Test:** Start daemon, then send `kill -TERM <pid>` or Ctrl+C
**Expected:** Clean exit, no error output, no orphaned TCP connections
**Why human:** Requires running daemon with real evdev device to verify resource cleanup

### Gaps Summary

No automated verification gaps found. All 5 roadmap success criteria are verified at the code level:

- listener.py correctly pairs MSC_SCAN events with EV_KEY events and dispatches to CommandMapper
- find_ir_device() polls by device name with configurable timeout
- __main__.py wires the full pipeline: config -> CommandMapper -> listener -> ADCP
- Discover mode prints scancodes without creating a CommandMapper
- Signal handlers cancel the main task; finally blocks close the device

All 6 requirements (IRC-01, IRC-02, IRC-03, DEV-01, DEV-03, DEV-04) have supporting test coverage. 62 tests pass with no regressions.

The remaining verification items require physical hardware (RPi + TSOP38238 sensor + Sony remote + projector on network) and cannot be tested programmatically on the development machine.

---

_Verified: 2026-04-09T23:00:00Z_
_Verifier: Claude (gsd-verifier)_
