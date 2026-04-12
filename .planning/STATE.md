---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: completed
stopped_at: Phase 4 context gathered
last_updated: "2026-04-12T01:31:25.183Z"
last_activity: 2026-04-11
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 7
  completed_plans: 4
  percent: 57
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-09)

**Core value:** Press a button on the Sony remote, the projector responds -- the IR receiver works again.
**Current focus:** Phase 04 — deployment-and-hardening (next up)

## Current Position

Phase: 3 (complete — hardware verified)
Plan: 2 of 2 complete
Status: Complete
Last activity: 2026-04-11

Progress: [########..] 86%

## Performance Metrics

**Velocity:**

- Total plans completed: 6
- Average duration: ~1.5 min/plan
- Total execution time: ~9 minutes

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3/3 | ~5 min | ~1.5 min |
| 02 | 2/2 | ~3 min | ~1.5 min |
| 03 | 2/2 | ~6 min | ~3 min |

**Recent Trend:**

- Last 5 plans: 01-P3, 02-P1, 02-P2, 03-P1, 03-P2
- Trend: Stable ~2-4 min/plan

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: Merged config system into Phase 1 with ADCP client (config is thin, ~50 lines of dataclasses)
- WiFi bridge removed — projector on home network at 192.168.1.80
- 03-01: Used sys.modules patching for evdev mocks (lazy import inside function requires injecting into sys.modules)
- 03-01: Scancodes extracted from EV_MSC/MSC_SCAN events, not EV_KEY.code (raw IR scancodes match config keys)
- [Phase 03]: Lazy evdev.ecodes import in _discover_loop() with ImportError fallback for cross-platform compatibility

### Pending Todos

None yet.

### Blockers/Concerns

- Projector must have "Network Standby" enabled or ADCP is unreachable in deep standby
- ir-keytable -p sony must be run after each reboot (Phase 4 will fix via systemd)
- ADCP commands blocked while projector OSD menu is open
- Some remote buttons unmapped (test pattern, 3D, color space, RCP, gamma)

## Session Continuity

Last session: 2026-04-12T01:31:25.181Z
Stopped at: Phase 4 context gathered
Resume file: .planning/phases/04-deployment-and-hardening/04-CONTEXT.md
