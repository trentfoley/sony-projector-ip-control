---
phase: 2
slug: command-mapper
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-10
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with pytest-asyncio |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]` section) |
| **Quick run command** | `python -m pytest tests/test_mapper.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_mapper.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | MAP-02, MAP-03, MAP-04, MAP-05 | — | N/A | unit | `python -m pytest tests/test_mapper.py -x -q` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | MAP-02 | — | N/A | unit | `python -m pytest tests/test_mapper.py::test_non_repeat_ignores_hold -x -q` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | MAP-03 | — | N/A | unit | `python -m pytest tests/test_mapper.py::test_repeat_fires_on_hold -x -q` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 1 | MAP-04 | — | N/A | unit | `python -m pytest tests/test_mapper.py::test_unknown_scancode_logged -x -q` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 1 | MAP-05 | — | N/A | unit | `python -m pytest tests/test_mapper.py::test_rate_limit -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_mapper.py` — stubs for MAP-02, MAP-03, MAP-04, MAP-05
- Existing `tests/conftest.py` — shared fixtures (already present from Phase 1)
- Test framework already installed (pytest, pytest-asyncio in dev deps)

*Existing infrastructure covers framework requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Held button on physical remote fires at kernel repeat rate | MAP-03 | Requires Pi + IR sensor hardware | Hold menu-up on remote, observe ADCP sends in daemon log |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
