# Phase 4: Deployment and Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-11
**Phase:** 04-deployment-and-hardening
**Areas discussed:** Service configuration, Install script scope, Watchdog behavior

---

## Service Configuration

### Service Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Single service | One projector-bridge.service with ExecStartPre for ir-keytable | ✓ |
| Two services | Separate ir-setup.service (oneshot) + projector-bridge.service | |

**User's choice:** Single service
**Notes:** Simpler, fewer moving parts

### Service User

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated user | Create 'projector-bridge' system user with input group | |
| Your user (trent) | Run as existing user, already has permissions and venv | ✓ |
| Root | No permission issues but unnecessary privilege | |

**User's choice:** Run as trent
**Notes:** Venv and repo already in /home/trent/

---

## Install Script Scope

### Script Coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Full setup | apt install, venv, pip, systemd unit, enable service | ✓ |
| Daemon only | Just venv + pip + systemd, assume ir-keytable manual | |
| Minimal | Just systemd unit file | |

**User's choice:** Full setup
**Notes:** One command from git clone to running daemon

### Config Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Never overwrite | Skip existing config, install .example for reference | ✓ |
| Prompt | Ask before replacing existing config | |
| Always overwrite | Replace config every run | |

**User's choice:** Never overwrite
**Notes:** Preserve user's customized config

---

## Watchdog Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| systemd restart only | Restart=always + RestartSec=3, no watchdog | ✓ |
| sd_notify watchdog | Python heartbeats, systemd detects hangs | |
| Hardware watchdog + sd_notify | Full chain: Python → systemd → hardware reboot | |

**User's choice:** systemd restart only
**Notes:** Handles 95% of failure modes. INFRA-04 descoped from v1.

## Claude's Discretion

- Service file details (Type, resource limits, environment vars)
- Install script structure and error handling
- Whether to include an uninstall option

## Deferred Ideas

None
