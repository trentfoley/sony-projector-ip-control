---
phase: 04-deployment-and-hardening
plan: 01
subsystem: deployment
tags: [systemd, install-script, deployment, infrastructure]
dependency_graph:
  requires: [03-01, 03-02]
  provides: [systemd-service, install-script, example-config]
  affects: [projector-bridge.service, install.sh, projector-bridge.yaml.example]
tech_stack:
  added: [systemd]
  patterns: [ExecStartPre-for-setup, idempotent-install, config-overwrite-guard]
key_files:
  created:
    - projector-bridge.service
    - projector-bridge.yaml.example
    - install.sh
  modified: []
decisions:
  - "Type=exec chosen over Type=simple for better exec error reporting (systemd 252+)"
  - "Security hardening: ProtectSystem=strict, ProtectHome=read-only, NoNewPrivileges, PrivateTmp"
  - "Config chmod 600 for password protection"
metrics:
  duration: 95s
  completed: "2026-04-11"
  tasks: 2
  files_created: 3
  files_modified: 0
---

# Phase 04 Plan 01: Systemd Service and Install Script Summary

systemd unit with security hardening, example config, and idempotent install script for single-command RPi deployment

## What Was Built

### Task 1: systemd service unit and example config (88ab2bc)

Created `projector-bridge.service` implementing all 8 locked decisions (D-01 through D-08):
- Type=exec with User=trent, Group=input for /dev/input access
- ExecStartPre runs ir-keytable to set Sony IR protocol before daemon starts
- Restart=always with RestartSec=3 for crash recovery (INFRA-04 watchdog explicitly descoped per D-03)
- After=network-online.target ensures network is available for ADCP connection
- Security hardening: ProtectSystem=strict, ProtectHome=read-only, NoNewPrivileges=true, PrivateTmp=true
- StandardOutput/StandardError=journal for journald log capture (D-08)

Created `projector-bridge.yaml.example` as a reference config mirroring the production config structure with password set to empty string.

### Task 2: Idempotent install script (6c2b5d9)

Created `install.sh` handling full deployment lifecycle:
1. Checks for gpio-ir overlay in /boot/firmware/config.txt (warns if missing, D-07)
2. Installs system dependencies (ir-keytable via apt)
3. Creates Python venv and installs package in editable mode
4. Deploys config from example only if no config exists (D-06 overwrite guard)
5. Sets chmod 600 on config file for password protection (T-04-01)
6. Deploys systemd unit, daemon-reload, enable, and restart

All steps are idempotent -- safe to re-run after git pull or config changes.

## Threat Mitigations Implemented

| Threat ID | Mitigation |
|-----------|------------|
| T-04-01 | chmod 600 on config file in install.sh |
| T-04-02 | User=trent, NoNewPrivileges=true, ProtectSystem=strict, PrivateTmp=true in service file |
| T-04-05 | ir-keytable failure is fatal (no `-` prefix) but Restart=always retries after 3s |

## Deviations from Plan

None -- plan executed exactly as written.

## Verification Results

- Service file parses as valid INI with all required sections and values
- Example config parses as valid YAML with projector, ir, and mappings sections
- Install script contains all required deployment steps and safety guards
- No WatchdogSec or sd_notify references (INFRA-04 descoped)
- All 65 existing tests pass

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 88ab2bc | systemd service unit and example config |
| 2 | 6c2b5d9 | idempotent install script |

## Self-Check: PASSED

- All 3 created files exist on disk
- Both task commits (88ab2bc, 6c2b5d9) verified in git log
