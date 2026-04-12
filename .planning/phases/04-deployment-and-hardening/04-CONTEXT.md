# Phase 4: Deployment and Hardening - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the working IR bridge start automatically on boot and recover from crashes without manual intervention. Deliver a single install script that takes a fresh Pi from git clone to running daemon.

</domain>

<decisions>
## Implementation Decisions

### Service Configuration
- **D-01:** Single systemd service `projector-bridge.service` — no separate ir-setup unit. ExecStartPre runs `ir-keytable -s rc0 -p sony` to set the IR protocol before the daemon starts.
- **D-02:** Run as user `trent` (existing user). The repo, venv, and config are already in `/home/trent/sony-projector-ip-control`. Add `Group=input` for /dev/input access.
- **D-03:** `Restart=always`, `RestartSec=3`. No sd_notify watchdog, no hardware watchdog. systemd restart handles crash recovery. INFRA-04 (hardware watchdog) is descoped from v1.
- **D-04:** `After=network-online.target` — ADCP needs network to reach projector at 192.168.1.80.

### Install Script
- **D-05:** `install.sh` handles full setup: `apt install ir-keytable`, create venv, `pip install -e .`, deploy systemd unit, `systemctl enable`. Idempotent for re-runs.
- **D-06:** Never overwrite existing `projector-bridge.yaml`. Install a `.example` file for reference. If no config exists at the target location, copy the example as the default.
- **D-07:** Install script assumes gpio-ir overlay is already configured in `/boot/firmware/config.txt` (dtoverlay=gpio-ir,gpio_pin=18). Print a warning if not found, but don't modify boot config automatically.

### Logging
- **D-08:** Carried from Phase 3: plain text logging to stderr. systemd journald captures it automatically. No custom log files or rotation. View with `journalctl -u projector-bridge`.

### Claude's Discretion
- Service file details (Type=simple vs exec, resource limits, environment vars)
- Install script structure and error handling
- Whether to include an uninstall option

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Code
- `src/projector_bridge/__main__.py` — CLI entry point, must match ExecStart command
- `projector-bridge.yaml` — production config, install script must handle this
- `run.sh` — current manual run script, install.sh replaces this for production
- `pyproject.toml` — package metadata, console_scripts entry point

### Prior Phase Decisions
- `.planning/phases/03-ir-listener-and-application/03-CONTEXT.md` — D-06 (exit on device loss, let systemd restart), D-08 (plain text logging, journald)

### System Configuration
- `/boot/firmware/config.txt` — must have `dtoverlay=gpio-ir,gpio_pin=18`
- ir-keytable protocol: `ir-keytable -s rc0 -p sony` (must run after each boot)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `run.sh` — contains venv creation and pip install logic, can inform install.sh
- `pyproject.toml` — defines `projector-bridge` console script entry point

### Established Patterns
- Config search path: `projector-bridge.yaml` in CWD, then `/etc/projector-bridge/config.yaml`
- Device auto-detection by name "gpio_ir_recv" (no hardcoded paths)

### Integration Points
- ExecStart should use the venv's python or the console_scripts entry point
- ExecStartPre runs ir-keytable to set sony protocol
- WorkingDirectory should be the repo root so config search finds projector-bridge.yaml

</code_context>

<specifics>
## Specific Ideas

- Pi hostname is `pi3.local`, SSH user is `trent`
- Projector IP is 192.168.1.80 on the home network (no WiFi bridge needed)
- Config file lives in the repo root as `projector-bridge.yaml`

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-deployment-and-hardening*
*Context gathered: 2026-04-11*
