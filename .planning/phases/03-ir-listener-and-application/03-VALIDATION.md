---
phase: 3
slug: ir-listener-and-application
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | IRC-01 | — | N/A | unit | `python -m pytest tests/test_listener.py -x -q` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | IRC-02 | — | N/A | unit | `python -m pytest tests/test_listener.py -x -q` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | IRC-03 | — | N/A | unit | `python -m pytest tests/test_listener.py -x -q` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | DEV-01 | — | N/A | unit | `python -m pytest tests/test_main.py -x -q` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | DEV-03 | — | N/A | unit | `python -m pytest tests/test_main.py -x -q` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 1 | DEV-04 | — | N/A | unit | `python -m pytest tests/test_main.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_listener.py` — stubs for IRC-01, IRC-02, IRC-03 (evdev listener tests)
- [ ] `tests/test_main.py` — stubs for DEV-01, DEV-03, DEV-04 (CLI entry point, discover mode, shutdown tests)
- [ ] `tests/conftest.py` — shared evdev mock fixtures (InputDevice, async_read_loop, ecodes)

*Existing test infrastructure (pytest, pytest-asyncio) already configured in pyproject.toml.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real IR button press triggers projector response | IRC-01 | Requires physical IR sensor + Sony remote + projector | Press power button on Sony remote, verify projector toggles power |
| Device auto-detection on real hardware | IRC-02 | Requires gpio_ir_recv kernel device | Boot Pi, verify listener finds /dev/input/eventN by name |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
