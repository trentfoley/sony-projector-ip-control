# Retrospective

## Milestone: v1.0 — MVP

**Shipped:** 2026-04-12
**Phases:** 4 | **Plans:** 8

### What Was Built
- ADCP TCP client with SHA256 challenge-response auth and typed error handling
- Command mapper with debounce/repeat logic and 100ms global rate limiting
- Async IR listener via kernel gpio-ir + evdev with polling device discovery
- CLI entry point with discover mode, graceful shutdown, and YAML config
- systemd service with security hardening, idempotent install script, crash recovery

### What Worked
- Data-flow-ordered phases (config -> ADCP -> mapper -> listener -> deploy) meant each phase built on solid foundations
- Mock ADCP server in Phase 1 enabled all development without projector hardware
- Kernel gpio-ir + evdev was the right call — reliable, no timing issues, clean async integration
- Open-per-command ADCP model kept the client simple and avoided stale connection bugs
- Human UAT on the Pi caught nothing — automated tests were comprehensive

### What Was Inefficient
- Phase 1 SUMMARY.md files not on disk (predates tracking or were lost) — minor gap in audit trail
- REQUIREMENTS.md traceability table fell stale quickly — many items marked "Pending" that were completed
- WiFi bridge phase had to be removed mid-roadmap when requirements changed

### Patterns Established
- sys.modules patching for evdev mocks (lazy imports require injection)
- EV_MSC/MSC_SCAN events for raw IR scancodes (not EV_KEY.code)
- Lazy ecodes import with ImportError fallback for cross-platform compatibility
- Type=exec systemd units for better error reporting

### Key Lessons
- Embedded daemon projects benefit from mock servers early — enables full TDD without hardware
- Kernel subsystems (gpio-ir, evdev) are more reliable than userspace alternatives for timing-sensitive work
- Open-per-command is simpler than connection pooling when the device has idle timeouts
- 65 tests across 4 phases with zero regressions — layered testing works

### Cost Observations
- Sessions: ~6 across 4 days
- Model mix: primarily Opus for execution, Sonnet for verification/review
- Notable: Small phase count (4) with well-scoped plans kept total execution fast (~15 min agent time)

## Cross-Milestone Trends

| Metric | v1.0 |
|--------|------|
| Phases | 4 |
| Plans | 8 |
| LOC (Python) | 1,963 |
| Tests | 65 |
| Timeline | 4 days |
| Regressions | 0 |
