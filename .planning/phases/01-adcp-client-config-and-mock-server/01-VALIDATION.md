---
phase: 1
slug: adcp-client-config-and-mock-server
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-10
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with pytest-asyncio |
| **Config file** | `pyproject.toml` (Wave 0 creates) |
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
| 1-01-01 | 01 | 1 | MAP-01 | — | N/A | unit | `python -m pytest tests/test_config.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | ADCP-01 | — | N/A | integration | `python -m pytest tests/test_adcp.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | ADCP-02 | — | N/A | integration | `python -m pytest tests/test_adcp.py::test_sha256_auth -x -q` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 1 | ADCP-03 | — | N/A | integration | `python -m pytest tests/test_adcp.py::test_retry -x -q` | ❌ W0 | ⬜ pending |
| 1-02-04 | 02 | 1 | ADCP-04 | — | N/A | integration | `python -m pytest tests/test_adcp.py::test_error_parsing -x -q` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 1 | DEV-02 | — | N/A | integration | `python -m pytest tests/test_mock_server.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — project config with pytest/pytest-asyncio deps
- [ ] `tests/conftest.py` — shared fixtures (mock_projector, sample config)
- [ ] `tests/test_config.py` — stubs for MAP-01 config validation
- [ ] `tests/test_adcp.py` — stubs for ADCP-01 through ADCP-04
- [ ] `tests/test_mock_server.py` — stubs for DEV-02

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
