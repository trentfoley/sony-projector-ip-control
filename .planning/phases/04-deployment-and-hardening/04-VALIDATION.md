---
phase: 4
slug: deployment-and-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-11
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | INFRA-02 | — | N/A | integration | `systemctl is-enabled projector-bridge` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | INFRA-03 | — | N/A | integration | `bash install.sh && systemctl status projector-bridge` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | INFRA-02 | — | N/A | unit | `python -m pytest tests/ -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Existing test infrastructure covers Python code changes
- [ ] systemd and install.sh validation is manual (on-device)

*Existing infrastructure covers Python-side requirements. Infrastructure files (systemd, install.sh) require on-device validation.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Service starts on boot | INFRA-02 | Requires reboot of physical Pi | Reboot Pi, verify `systemctl status projector-bridge` shows active |
| Install script on fresh OS | INFRA-03 | Requires clean Bookworm image | Run `install.sh` on fresh Pi, verify service is running |
| Service restarts after crash | INFRA-02 | Requires killing process on Pi | `kill -9 $(pidof python3)`, wait 3s, verify service restarted |

*Infrastructure validation requires physical Raspberry Pi hardware.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
