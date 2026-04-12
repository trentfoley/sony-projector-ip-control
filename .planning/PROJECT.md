# Sony Projector IR-to-ADCP Bridge

## What This Is

A Python daemon running on a Raspberry Pi 3B that restores remote control functionality to a Sony VPL-XW5000ES projector with a broken IR receiver. It receives Sony SIRC IR commands via a KY-022 (VS1838B) IR sensor and translates them into ADCP (Advanced Display Control Protocol) commands sent over TCP to the projector. Deployed as a systemd service with automatic crash recovery and one-command installation.

## Core Value

Press a button on the Sony remote, the projector responds — the IR receiver works again.

## Requirements

### Validated

- [x] ADCP client connects to projector on TCP:53595 with SHA256 challenge-response auth — Validated in Phase 1: ADCP Client, Config, and Mock Server
- [x] Scancode-to-ADCP command mapping is configurable via YAML — Validated in Phase 1: Config system
- [x] Mock ADCP server enables development and testing without the projector — Validated in Phase 1: Mock Server
- [x] Debounce/repeat logic prevents projector flooding while supporting held buttons — Validated in Phase 2: Command Mapper
- [x] IR commands received via kernel gpio-ir overlay + evdev on GPIO 18 — Validated in Phase 3: IR Listener
- [x] Power on/off, input switching, menu navigation, and blanking work from the remote — Validated in Phase 3: Application wiring
- [x] Discover mode prints raw scancodes to aid mapping new remote buttons — Validated in Phase 3: Application wiring
- [x] systemd service auto-starts IR bridge on boot with crash recovery — Validated in Phase 4: Deployment and Hardening (human UAT passed 2026-04-12)

### Active

None — all v1.0 requirements shipped.

### Out of Scope

- Web UI or REST API for projector control — remote control is the interface
- Motorized lens control — XW5000ES has a manual lens (hardware limitation)
- Home Assistant or smart home integration — standalone daemon only
- Multi-projector support — single projector, single Pi
- WiFi-to-Ethernet NAT bridge — removed, projector connected directly to home network (192.168.1.80)
- Hardware watchdog (sd_notify/WatchdogSec) — descoped per D-03, systemd Restart=always is sufficient

## Context

- **Projector**: Sony VPL-XW5000ES, ADCP over TCP:53595, ASCII protocol with `\r\n` termination
- **Auth**: SHA256 challenge-response (or NOKEY if auth disabled in projector settings)
- **IR protocol**: Sony SIRC (12, 15, or 20-bit — kernel tries all when protocol=sony)
- **Hardware**: KY-022 (VS1838B) IR sensor wired to RPi 3B GPIO 18 (3.3V, onboard pull-up on module)
- **Network**: Projector connected directly to home network via ethernet at 192.168.1.80
- **Reference implementations**: tokyotexture/homeassistant-custom-components (SONY_ADCP.py), kennymc-c/ucr-integration-sonyADCP (most complete, has SHA256 auth)
- **Risk**: Remote's exact SIRC scancodes are undocumented — mitigated by discover mode
- **Risk**: Projector may reject ADCP in deep standby — requires "Network Standby" enabled in projector settings

## Constraints

- **Hardware**: Raspberry Pi 3B (existing), KY-022 (VS1838B) IR sensor on GPIO 18
- **Stack**: Python 3 with asyncio, pyyaml, evdev — minimal dependencies for embedded use
- **IR decoding**: Kernel gpio-ir overlay + ir-keytable (not pigpio — unreliable userspace timing)
- **Connection model**: Open-per-command (connect → auth → send → close) due to projector's 60s idle timeout
## Current State

Shipped v1.0 with 1,963 LOC Python across 4 phases (8 plans) in 4 days.
Tech stack: Python 3.11, asyncio, evdev, PyYAML, systemd.
Running on Raspberry Pi 3B, deployed via `install.sh`, auto-starts on boot.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Kernel gpio-ir over pigpio | Battle-tested, interrupt-driven vs unreliable userspace timing | ✓ Good — reliable IR decoding, no timing issues |
| Python evdev over triggerhappy | Avoids per-press shell spawn latency | ✓ Good — async_read_loop integrates natively with asyncio |
| Open-per-command ADCP | Projector has 60s idle timeout, auth is per-connection anyway | ✓ Good — simple, reliable, no stale connection issues |
| asyncio event loop | Non-blocking IR listen + ADCP send in single process | ✓ Good — clean architecture, single daemon |
| sys.modules patching for evdev mocks | Lazy import inside function requires injecting into sys.modules | ✓ Good — enables cross-platform testing without evdev hardware |
| EV_MSC/MSC_SCAN for scancodes | Raw IR scancodes from MSC_SCAN match config keys | ✓ Good — correct approach for IR protocol scancodes |
| Type=exec over Type=simple | Better exec error reporting, available on systemd 252 | ✓ Good — clearer failure diagnostics |
| INFRA-04 descoped (no watchdog) | Restart=always with RestartSec=3 is sufficient for home use | ✓ Good — simpler, crash recovery confirmed in UAT |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-12 after v1.0 milestone completion*
