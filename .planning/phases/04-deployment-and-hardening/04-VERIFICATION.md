---
phase: 04-deployment-and-hardening
verified: 2026-04-11T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Cold-boot the Raspberry Pi and verify projector-bridge.service is active without any manual steps"
    expected: "systemctl is-active projector-bridge returns 'active' within ~15 seconds of boot"
    why_human: "Requires physical Raspberry Pi hardware to test boot-time service activation"
  - test: "Run install.sh on a fresh Raspberry Pi OS Bookworm image (or a clean clone) and verify the service starts"
    expected: "Script completes without errors; systemctl status projector-bridge shows active; second run also completes without errors"
    why_human: "Idempotency and fresh-install behavior require real RPi hardware with apt and systemd"
  - test: "Kill the daemon with SIGKILL and verify it restarts within ~3 seconds"
    expected: "sudo systemctl kill --signal=SIGKILL projector-bridge; sleep 4; systemctl is-active projector-bridge returns 'active'"
    why_human: "Restart=always behavior requires live systemd on real hardware"
---

# Phase 4: Deployment and Hardening Verification Report

**Phase Goal:** The IR bridge starts automatically on boot and recovers from crashes without manual intervention
**Verified:** 2026-04-11
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | systemd unit file defines a service that starts the IR bridge daemon on boot | VERIFIED | projector-bridge.service exists with WantedBy=multi-user.target, After=network-online.target, Wants=network-online.target, Restart=always, RestartSec=3; commit 88ab2bc |
| 2 | install.sh deploys all dependencies, code, config, and services on a fresh RPi | VERIFIED | install.sh (755) contains apt install ir-keytable, python3 -m venv, pip install -e ., sudo cp service, systemctl daemon-reload, systemctl enable, systemctl restart; commit 6c2b5d9 |
| 3 | install.sh is idempotent -- running it twice produces no errors | VERIFIED | venv creation gated on `if [ ! -d "$VENV_DIR" ]`; pip install -e . is always safe to re-run; systemctl enable and restart are idempotent; config copy gated on file absence |
| 4 | Existing config files are never overwritten by install.sh | VERIFIED | D-06 guard: `if [ ! -f "$CONFIG_FILE" ]` wraps the cp from example; else branch applies chmod 600 without touching content |
| 5 | INFRA-04 (hardware watchdog) is descoped per D-03 -- only Restart=always is implemented | VERIFIED | No WatchdogSec or sd_notify in projector-bridge.service or install.sh (grep confirmed empty); roadmap SC #4 explicitly acknowledges descope |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `projector-bridge.service` | systemd unit file for the IR bridge daemon | VERIFIED | All 3 INI sections present; ExecStartPre=/usr/bin/ir-keytable -s rc0 -p sony; ExecStart uses .venv/bin/projector-bridge; Restart=always, RestartSec=3, User=trent, Group=input |
| `projector-bridge.yaml.example` | Reference config file for deployment | VERIFIED | Valid YAML; contains projector, ir, mappings keys; host: "192.168.1.80"; password: "" |
| `install.sh` | Idempotent deployment script | VERIFIED | Executable (mode 755); contains systemctl enable, systemctl restart, all 6 deployment steps |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `projector-bridge.service` | `.venv/bin/projector-bridge` | ExecStart path | WIRED | ExecStart=/home/trent/sony-projector-ip-control/.venv/bin/projector-bridge --log-level INFO (line 12 of service file) |
| `install.sh` | `projector-bridge.service` | cp to /etc/systemd/system/ | WIRED | `sudo cp "$SERVICE_FILE" "$SYSTEMD_DIR/"` (line 59 of install.sh) |

### Data-Flow Trace (Level 4)

Not applicable -- phase artifacts are infrastructure files (systemd unit, shell script, config template), not components that render dynamic data.

### Behavioral Spot-Checks

Step 7b: SKIPPED (requires Linux systemd and Raspberry Pi hardware -- not runnable on Windows dev machine)

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INFRA-02 | 04-01-PLAN.md | systemd services auto-start IR bridge on boot with Restart=always | SATISFIED | projector-bridge.service: WantedBy=multi-user.target (boot autostart), Restart=always (crash recovery) |
| INFRA-03 | 04-01-PLAN.md | Install script deploys all dependencies, code, config, and services on a fresh RPi | SATISFIED | install.sh covers all 6 steps: apt, venv, pip, config, systemd deploy, enable+restart |
| INFRA-04 | 04-01-PLAN.md | Hardware watchdog reboots the Pi if the daemon hangs | DESCOPED | Per D-03 and roadmap SC #4: INFRA-04 is explicitly out of scope for v1. Restart=always handles crash recovery; hang detection not implemented. |

**Traceability discrepancy noted:** REQUIREMENTS.md maps INFRA-02, INFRA-03, INFRA-04 to "Phase 5" but the ROADMAP and PLAN frontmatter assign them to Phase 4. The RESEARCH.md flagged this discrepancy and states "The CONTEXT.md (user decisions) governs." The ROADMAP is the authoritative source for phase assignment. REQUIREMENTS.md traceability table is stale and should be updated to reflect Phase 4.

**Orphaned requirements check:** No REQUIREMENTS.md traceability entries point to Phase 4 (the table incorrectly says Phase 5 for all three). No additional requirements are mapped to Phase 4 in the traceability table. No orphaned requirements beyond the noted stale mapping.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | -- | -- | -- | No anti-patterns detected |

No TODOs, FIXMEs, placeholders, stub patterns, or empty implementations found in any phase artifact.

### Human Verification Required

### 1. Boot-time Service Auto-Start

**Test:** Cold-boot the Raspberry Pi and check service status after boot completes
**Expected:** `systemctl is-active projector-bridge` returns `active` without any manual steps
**Why human:** Requires physical Raspberry Pi with gpio-ir overlay configured in /boot/firmware/config.txt; boot-time ordering behavior cannot be verified on a development machine

### 2. Fresh Install from Scratch

**Test:** On a fresh Raspberry Pi OS Bookworm image (or clean user account), run `bash install.sh` followed immediately by `bash install.sh` a second time
**Expected:** Both runs complete without errors; `systemctl status projector-bridge` shows active after first run; second run produces no failures
**Why human:** apt install, systemctl, and real filesystem state are required to verify idempotency; these are unavailable on a Windows dev machine

### 3. Crash Recovery (Restart=always)

**Test:** With the daemon running, execute `sudo systemctl kill --signal=SIGKILL projector-bridge`, wait 4 seconds, check `systemctl is-active projector-bridge`
**Expected:** Service returns to `active` within 3-4 seconds (RestartSec=3)
**Why human:** Requires live systemd and a running service to test restart behavior

### Gaps Summary

No automated verification gaps. All 5 must-have truths are confirmed by direct inspection of the three artifacts:

- projector-bridge.service contains every required directive: Type=exec, User=trent, Group=input, ExecStartPre with ir-keytable, ExecStart with venv entry point, Restart=always, RestartSec=3, After/Wants=network-online.target, WantedBy=multi-user.target, no WatchdogSec
- projector-bridge.yaml.example is valid YAML with projector/ir/mappings sections and empty password field
- install.sh (mode 755) covers all 6 deployment steps with D-06 config overwrite protection, D-07 gpio-ir warning, chmod 600 security, and idempotent step design
- Both commit hashes (88ab2bc, 6c2b5d9) confirmed in git history
- Full test suite: 65/65 tests pass with no regressions

Three items require human verification on physical Raspberry Pi hardware: boot-time auto-start, fresh-install idempotency, and crash recovery restart behavior.

The REQUIREMENTS.md traceability table maps INFRA-02/03/04 to "Phase 5" instead of Phase 4 -- this is a documentation artifact that should be corrected but does not affect goal achievement.

---

_Verified: 2026-04-11_
_Verifier: Claude (gsd-verifier)_
