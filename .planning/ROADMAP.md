# Roadmap: Sony Projector IR-to-ADCP Bridge

## Overview

This roadmap delivers a working IR-to-ADCP bridge in four phases, ordered by the data flow pipeline: config and ADCP communication first (the critical path that talks to the projector), then command translation logic, then IR reception and full application wiring, and finally deployment hardening. Phases 1-3 require no Pi hardware and can be developed and tested on any machine against the mock server. Phase 4 wraps a working system in production-ready packaging.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: ADCP Client, Config, and Mock Server** - Project foundation, YAML config system, TCP client with SHA256 auth, and mock projector for testing
- [ ] **Phase 2: Command Mapper** - Scancode-to-ADCP translation with debounce, repeat handling, and rate limiting
- [ ] **Phase 3: IR Listener and Application** - evdev IR reception, discover mode, full pipeline wiring, and graceful shutdown
- ~~**Phase 4: WiFi Bridge**~~ - REMOVED: Projector connected directly to home network via ethernet (192.168.1.80)
- [ ] **Phase 4: Deployment and Hardening** - systemd services, install script, and hardware watchdog for unattended operation

## Phase Details

### Phase 1: ADCP Client, Config, and Mock Server
**Goal**: Developer can send ADCP commands to a mock projector from the command line, with all settings driven by a YAML config file
**Depends on**: Nothing (first phase)
**Requirements**: MAP-01, ADCP-01, ADCP-02, ADCP-03, ADCP-04, DEV-02
**Success Criteria** (what must be TRUE):
  1. Running the mock server and sending a power-on command via the ADCP client succeeds with SHA256 auth
  2. Running the mock server with NOKEY mode and sending a command succeeds without auth
  3. Changing projector host, port, password, or command mappings in config.yaml takes effect without code changes
  4. Client retries a transient connection failure and logs typed error codes for auth/command/value errors
  5. Config validates and rejects malformed YAML with a clear error message
**Plans**: TBD

### Phase 2: Command Mapper
**Goal**: Scancodes translate to correct ADCP commands with proper debounce and rate limiting so the projector is never flooded
**Depends on**: Phase 1
**Requirements**: MAP-02, MAP-03, MAP-04, MAP-05
**Success Criteria** (what must be TRUE):
  1. A non-repeating command (e.g., power) fires exactly once per button press, even when the button is held
  2. A repeatable command (e.g., menu-up) fires continuously when held, with a minimum 100ms gap between sends
  3. An unknown scancode is logged at INFO level with its hex value, not silently dropped
  4. Rapid successive button presses never produce ADCP sends closer than 100ms apart
**Plans**: 2 (02-01 implementation, 02-02 tests)

### Phase 3: IR Listener and Application
**Goal**: User can press buttons on the Sony remote and the projector responds, with discover mode available for mapping new buttons
**Depends on**: Phase 2
**Requirements**: IRC-01, IRC-02, IRC-03, DEV-01, DEV-03, DEV-04
**Success Criteria** (what must be TRUE):
  1. Pressing the power button on the Sony remote powers the projector on or off
  2. Pressing menu navigation buttons (up/down/left/right/enter/back) on the remote navigates projector menus
  3. Running with --discover prints raw scancodes to stdout without sending any ADCP commands
  4. The IR input device is found automatically by name (gpio_ir_recv) regardless of /dev/input path
  5. Sending SIGTERM or SIGINT to the daemon shuts it down cleanly, releasing TCP and evdev resources
**Plans**: 2 plans
Plans:
- [x] 03-01-PLAN.md — IR listener module (evdev device discovery + async event loop + tests)
- [x] 03-02-PLAN.md — CLI entry point, discover mode, signal handling + tests

### ~~Phase 4: WiFi Bridge~~ — REMOVED
Projector connected directly to home network via ethernet (192.168.1.80). WiFi bridge no longer needed.

### Phase 4: Deployment and Hardening
**Goal**: The complete system starts automatically on boot and recovers from hangs without manual intervention
**Depends on**: Phase 3
**Requirements**: INFRA-02, INFRA-03, INFRA-04
**Success Criteria** (what must be TRUE):
  1. After a cold boot, both the IR bridge and WiFi bridge are running without manual intervention
  2. Running the install script on a fresh Raspberry Pi OS Bookworm image results in a fully operational system
  3. If the IR bridge daemon hangs (stops notifying systemd), the Pi reboots itself within 30 seconds
  4. Services restart automatically after a crash (Restart=always)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. ADCP Client, Config, and Mock Server | 3/3 | Complete | 2026-04-10 |
| 2. Command Mapper | 2/2 | Complete | 2026-04-10 |
| 3. IR Listener and Application | 2/2 | Complete (hardware verification pending) | 2026-04-10 |
| ~~4. WiFi Bridge~~ | — | Removed | — |
| 4. Deployment and Hardening | 0/TBD | Not started | - |
