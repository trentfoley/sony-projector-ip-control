# Phase 4: Deployment and Hardening - Research

**Researched:** 2026-04-11
**Domain:** systemd service management, shell scripting, Raspberry Pi deployment
**Confidence:** HIGH

## Summary

Phase 4 creates two artifacts: a systemd service unit file (`projector-bridge.service`) and an idempotent install script (`install.sh`). Both are well-understood patterns with mature tooling on Raspberry Pi OS Bookworm.

The systemd unit is straightforward: `Type=exec` (available on Bookworm's systemd 252), `Restart=always`, `RestartSec=3`, `ExecStartPre` for ir-keytable protocol setup, and `ExecStart` using the venv's console_scripts entry point. The install script handles apt dependencies, venv creation, pip install, service file deployment, and enablement.

**Primary recommendation:** Use `Type=exec` for the systemd unit (better exec error reporting than Type=simple), and structure install.sh around idempotent operations with clear progress output.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Single systemd service `projector-bridge.service` -- no separate ir-setup unit. ExecStartPre runs `ir-keytable -s rc0 -p sony` to set the IR protocol before the daemon starts.
- **D-02:** Run as user `trent` (existing user). The repo, venv, and config are already in `/home/trent/sony-projector-ip-control`. Add `Group=input` for /dev/input access.
- **D-03:** `Restart=always`, `RestartSec=3`. No sd_notify watchdog, no hardware watchdog. systemd restart handles crash recovery. INFRA-04 (hardware watchdog) is descoped from v1.
- **D-04:** `After=network-online.target` -- ADCP needs network to reach projector at 192.168.1.80.
- **D-05:** `install.sh` handles full setup: `apt install ir-keytable`, create venv, `pip install -e .`, deploy systemd unit, `systemctl enable`. Idempotent for re-runs.
- **D-06:** Never overwrite existing `projector-bridge.yaml`. Install a `.example` file for reference. If no config exists at the target location, copy the example as the default.
- **D-07:** Install script assumes gpio-ir overlay is already configured in `/boot/firmware/config.txt` (dtoverlay=gpio-ir,gpio_pin=18). Print a warning if not found, but don't modify boot config automatically.
- **D-08:** Carried from Phase 3: plain text logging to stderr. systemd journald captures it automatically. No custom log files or rotation. View with `journalctl -u projector-bridge`.

### Claude's Discretion
- Service file details (Type=simple vs exec, resource limits, environment vars)
- Install script structure and error handling
- Whether to include an uninstall option

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-02 | systemd services auto-start IR bridge on boot with Restart=always | Systemd unit file pattern with Type=exec, Restart=always, RestartSec=3, WantedBy=multi-user.target. See Architecture Patterns section. |
| INFRA-03 | Install script deploys all dependencies, code, config, and services on a fresh RPi | install.sh pattern with idempotent apt/venv/pip/systemd steps. See Architecture Patterns section. |
| INFRA-04 | Hardware watchdog reboots the Pi if the daemon hangs | **DESCOPED from v1 per D-03.** Only systemd Restart=always is implemented. Note: REQUIREMENTS.md still lists this and the roadmap success criteria #3 references watchdog behavior -- this is a known discrepancy. |

**Discrepancy notes:**
- Roadmap success criteria #1 references "WiFi bridge" but INFRA-01 (WiFi NAT bridge) is not assigned to Phase 4. Projector is on ethernet per STATE.md. Phase 4 only addresses the IR bridge service.
- Roadmap success criteria #3 references "systemd watchdog reboots within 30 seconds" but D-03 explicitly descopes watchdog. The actual recovery mechanism is Restart=always with RestartSec=3 (crash restart, not hang detection).
- REQUIREMENTS.md traceability table maps INFRA-02/03/04 to "Phase 5" but the ROADMAP assigns them to Phase 4. The CONTEXT.md (user decisions) governs.
</phase_requirements>

## Standard Stack

No new libraries are needed for this phase. All tools are system-level:

### Core System Tools
| Tool | Source | Purpose | Why Standard |
|------|--------|---------|--------------|
| systemd 252 | Debian Bookworm built-in | Service management | Native init system on RPi OS Bookworm. Type=exec available since systemd 240. [VERIFIED: packages.debian.org/bookworm/systemd] |
| ir-keytable | `apt install ir-keytable` (v4l-utils) | IR protocol config | Standard Linux tool for RC device protocol/keymap configuration. [VERIFIED: CLAUDE.md stack] |
| bash | System shell | Install script | Available on all RPi OS installations. [ASSUMED] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Type=exec | Type=simple | simple is the default but doesn't report exec failures back to systemd. exec is strictly better when available (systemd >= 240). |
| install.sh | Ansible/Makefile | Over-engineered for a single-host deployment. Shell script is simpler and has zero dependencies. |
| Restart=always | WatchdogSec + sd_notify | Would detect hangs (not just crashes). Descoped from v1 per D-03. |

## Architecture Patterns

### Recommended Project Structure (new files)
```
/home/trent/sony-projector-ip-control/
  projector-bridge.service      # systemd unit file (checked into repo)
  install.sh                    # deployment script (checked into repo)
  projector-bridge.yaml         # production config (NOT in git, per existing .gitignore pattern)
  projector-bridge.yaml.example # reference config (checked into repo)
```

### Pattern 1: systemd Service Unit File

**What:** A systemd unit that starts the IR bridge daemon on boot with crash recovery.
**When to use:** Production deployment on the Raspberry Pi.

```ini
# Source: systemd.service(5) man page + project CONTEXT.md decisions
[Unit]
Description=Sony Projector IR-to-ADCP Bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
User=trent
Group=input
WorkingDirectory=/home/trent/sony-projector-ip-control
ExecStartPre=/usr/bin/ir-keytable -s rc0 -p sony
ExecStart=/home/trent/sony-projector-ip-control/.venv/bin/projector-bridge --log-level INFO
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

# Resource hardening (Claude's discretion)
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/trent/sony-projector-ip-control
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

**Key decisions reflected:**
- `ExecStartPre=/usr/bin/ir-keytable -s rc0 -p sony` -- sets Sony IR protocol before daemon starts (D-01)
- `User=trent`, `Group=input` -- existing user, input group for /dev/input access (D-02)
- `Restart=always`, `RestartSec=3` -- crash recovery without watchdog (D-03)
- `After=network-online.target` + `Wants=network-online.target` -- ensures network is up for ADCP TCP (D-04). The `Wants=` is needed so systemd actually waits for network-online.target to be reached. [CITED: systemd.io/NETWORK_ONLINE/]
- `WorkingDirectory` set to repo root so config search finds `projector-bridge.yaml` in CWD
- `ExecStart` uses the console_scripts entry point installed by `pip install -e .` in the venv

**On ProtectHome=read-only:** This allows the service to read its config and code from /home/trent but prevents writes to the home directory. `ReadWritePaths` is not strictly needed for this read-only daemon but is included in case future logging or state files are added. Could be omitted for simplicity. [ASSUMED]

### Pattern 2: Idempotent Install Script

**What:** A bash script that takes a fresh RPi from git clone to running daemon.
**When to use:** Initial deployment or re-deployment after changes.

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"
SERVICE_NAME="projector-bridge"
SERVICE_FILE="$REPO_DIR/$SERVICE_NAME.service"
SYSTEMD_DIR="/etc/systemd/system"
CONFIG_FILE="$REPO_DIR/projector-bridge.yaml"
EXAMPLE_FILE="$REPO_DIR/projector-bridge.yaml.example"

# 1. Check for gpio-ir overlay (D-07: warn but don't modify)
if ! grep -q "dtoverlay=gpio-ir" /boot/firmware/config.txt 2>/dev/null; then
    echo "WARNING: gpio-ir overlay not found in /boot/firmware/config.txt"
    echo "Add: dtoverlay=gpio-ir,gpio_pin=18"
fi

# 2. Install system dependencies
sudo apt-get update -qq
sudo apt-get install -y ir-keytable

# 3. Create venv + install package (idempotent)
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet -e "$REPO_DIR"

# 4. Deploy config (D-06: never overwrite existing)
if [ ! -f "$CONFIG_FILE" ] && [ -f "$EXAMPLE_FILE" ]; then
    cp "$EXAMPLE_FILE" "$CONFIG_FILE"
    echo "Created config from example: $CONFIG_FILE"
fi

# 5. Deploy systemd unit + enable
sudo cp "$SERVICE_FILE" "$SYSTEMD_DIR/"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

# 6. Start or restart
sudo systemctl restart "$SERVICE_NAME"
echo "Service $SERVICE_NAME is active:"
systemctl is-active "$SERVICE_NAME"
```

### Pattern 3: Example Config File

**What:** A `.example` config file checked into git as a reference. The real config lives at `projector-bridge.yaml` and is NOT in git (contains projector IP/password).
**Action:** Copy existing `projector-bridge.yaml` content to `projector-bridge.yaml.example`, stripping the password value.

### Anti-Patterns to Avoid
- **Modifying /boot/firmware/config.txt programmatically:** D-07 says warn only. Boot config changes require a reboot and can brick the system if done wrong.
- **Using `pip install` without venv:** Bookworm's externally-managed Python rejects bare `pip install`. Must use venv. [VERIFIED: CLAUDE.md constraints]
- **Hardcoding /dev/input/eventN in the service file:** The event number can change between boots. The daemon auto-detects by device name "gpio_ir_recv". [VERIFIED: existing code in listener.py]
- **Using `systemctl start` instead of `systemctl restart` in install.sh:** `start` is a no-op if the service is already running with old code. `restart` ensures the latest code is loaded.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Service management | Custom daemon/PID file/fork | systemd Type=exec | systemd handles lifecycle, logging, restart, boot ordering natively |
| Log rotation | Custom logrotate config | journald | journald handles log storage/rotation automatically for service stdout/stderr |
| IR protocol setup | Custom udev rules | ExecStartPre + ir-keytable | One-liner in the service file. Udev rules add complexity for no benefit in single-service use. |
| Dependency installation | Manual apt/pip steps | install.sh | Single entry point, idempotent, documents the process |

## Common Pitfalls

### Pitfall 1: ExecStartPre Failure Blocks Service Start
**What goes wrong:** If `ir-keytable -s rc0 -p sony` fails (e.g., rc0 doesn't exist yet), the service never starts.
**Why it happens:** The IR device may not be ready at boot time. gpio-ir overlay loads asynchronously.
**How to avoid:** The `-` prefix on ExecStartPre (`ExecStartPre=-/usr/bin/ir-keytable ...`) makes failure non-fatal. However, this means the daemon starts without the sony protocol set, which would cause silent failures. Better approach: keep it fatal and rely on `Restart=always` to retry after RestartSec. By the time the service restarts, the device is usually ready.
**Warning signs:** Service shows "failed" status immediately after boot. `journalctl -u projector-bridge` shows ir-keytable error.

### Pitfall 2: network-online.target Without Wants
**What goes wrong:** `After=network-online.target` alone only orders the service; it doesn't pull in the target. If nothing else Wants/Requires network-online.target, it may never be reached.
**Why it happens:** `After=` is ordering-only, not activation. [CITED: systemd.io/NETWORK_ONLINE/]
**How to avoid:** Include `Wants=network-online.target` in the [Unit] section alongside `After=`.
**Warning signs:** Service starts before the network is up. ADCP connection fails on first command but works after retry.

### Pitfall 3: pip install -e Without venv Activation
**What goes wrong:** Running `pip install -e .` outside the venv installs to system Python, which Bookworm blocks with "externally-managed-environment" error.
**Why it happens:** Bookworm enforces PEP 668 -- system Python refuses pip install without --break-system-packages.
**How to avoid:** Always use `"$VENV_DIR/bin/pip" install -e .` (explicit venv pip path). Never `source activate` in scripts -- it's fragile.
**Warning signs:** "error: externally-managed-environment" in install output.

### Pitfall 4: Config File Permissions
**What goes wrong:** The config file contains the projector password. If world-readable, it's a minor security concern on a single-user Pi.
**Why it happens:** Default umask creates files as 644.
**How to avoid:** Set `chmod 600 projector-bridge.yaml` in install.sh. The service runs as user trent who owns the file, so it can still read it.
**Warning signs:** `ls -la projector-bridge.yaml` shows world-readable with password in plaintext.

### Pitfall 5: Stale Service File After Git Pull
**What goes wrong:** After updating code via `git pull`, the systemd unit file in `/etc/systemd/system/` is still the old version.
**Why it happens:** The service file is copied, not symlinked. Changes in the repo don't propagate.
**How to avoid:** Re-run `install.sh` after any git pull that changes the service file. The script is idempotent. Alternative: use a symlink instead of copy, but this requires the repo to be on the same filesystem (which it is in this case).
**Warning signs:** Service behavior doesn't match the service file in the repo.

## Code Examples

### ExecStart Command Resolution
The `pyproject.toml` defines a console_scripts entry point:
```toml
[project.scripts]
projector-bridge = "projector_bridge.__main__:main"
```

After `pip install -e .` in the venv, this creates:
```
/home/trent/sony-projector-ip-control/.venv/bin/projector-bridge
```

ExecStart uses this directly -- no need for `python -m projector_bridge`. [VERIFIED: pyproject.toml in repo]

### Verifying Service Status
```bash
# Check service is running
systemctl status projector-bridge

# View recent logs
journalctl -u projector-bridge -n 50

# Follow logs in real time
journalctl -u projector-bridge -f

# Check boot-time startup
systemctl is-enabled projector-bridge
```

### Testing Restart Behavior
```bash
# Simulate crash -- kill the process, systemd should restart it
sudo systemctl kill --signal=SIGKILL projector-bridge
# Wait 3+ seconds, then check
systemctl is-active projector-bridge  # should be "active"
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ProtectHome=read-only works with ReadWritePaths for this use case | Architecture Patterns | Service may fail to start if systemd sandboxing prevents needed access. Easy to test and remove if problematic. |
| A2 | bash is available at /usr/bin/env bash on RPi OS Bookworm | Standard Stack | Extremely low risk -- bash is always present on Debian-based systems. |
| A3 | ir-keytable is in the `ir-keytable` apt package (not v4l-utils directly) | Standard Stack | May need `apt install v4l-utils` instead. Low risk -- install.sh will error visibly. |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-02 | Service file is valid systemd syntax | smoke | `systemd-analyze verify projector-bridge.service` (on Pi only) | N/A -- systemd tool, not pytest |
| INFRA-02 | Service restarts after crash | manual-only | Kill process, observe restart | N/A -- requires running service |
| INFRA-03 | install.sh runs without error on fresh Pi | manual-only | `bash install.sh` on target | N/A -- integration test on hardware |
| INFRA-03 | install.sh is idempotent | manual-only | Run install.sh twice, second run succeeds | N/A -- integration test on hardware |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q` (ensure existing tests still pass)
- **Per wave merge:** Full suite + manual service verification on Pi
- **Phase gate:** Service starts on boot, survives kill -9, install.sh runs clean on target

### Wave 0 Gaps
None -- this phase produces infrastructure files (service unit, shell script), not Python code. Existing tests verify the daemon code. New tests would be integration tests requiring the actual Raspberry Pi hardware, which are manual-only.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A (no user auth in deployment layer) |
| V3 Session Management | No | N/A |
| V4 Access Control | Yes | systemd User/Group isolation, ProtectSystem/ProtectHome sandboxing |
| V5 Input Validation | No | N/A (no new input paths in this phase) |
| V6 Cryptography | No | N/A |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| World-readable config with password | Information Disclosure | chmod 600 on config file |
| Service running as root | Elevation of Privilege | User=trent, NoNewPrivileges=true |
| Writable service file | Tampering | Deployed to /etc/systemd/system/ (root-owned) |
| Install script with sudo | Elevation of Privilege | Minimal sudo usage (apt, cp to /etc, systemctl only) |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Type=simple | Type=exec | systemd 240 (2019) | Better exec failure reporting |
| /boot/config.txt | /boot/firmware/config.txt | Bookworm (2023) | Path changed for firmware config on RPi |
| lircd for IR | Kernel RC subsystem + ir-keytable | Kernel 4.19 (2018) | No userspace daemon needed for IR decode |
| pip install (bare) | venv + pip install | PEP 668 / Bookworm (2023) | System Python refuses bare pip install |

## Open Questions

1. **ir-keytable apt package name**
   - What we know: ir-keytable is part of v4l-utils ecosystem
   - What's unclear: Whether `apt install ir-keytable` works or if the package is named differently on Bookworm
   - Recommendation: Install script should try `ir-keytable` first; if it's actually in `v4l-utils`, adjust. Easy to test on target.

2. **ProtectSystem=strict compatibility with ExecStartPre**
   - What we know: ProtectSystem=strict makes / read-only except for /etc, /dev, /proc, /sys
   - What's unclear: Whether ir-keytable in ExecStartPre needs write access to /sys/class/rc/
   - Recommendation: Start with ProtectSystem=strict. If ExecStartPre fails, relax to ProtectSystem=full or remove.

3. **Symlink vs copy for service file deployment**
   - What we know: Symlinks work for service files and auto-update on git pull. Copies require re-running install.sh.
   - What's unclear: Whether there are any systemd restrictions on symlinked unit files from home directories.
   - Recommendation: Use symlink (`ln -sf`) for convenience. If systemd rejects it, fall back to copy.

## Sources

### Primary (HIGH confidence)
- [Debian Bookworm systemd package](https://packages.debian.org/bookworm/systemd) -- confirmed systemd 252
- [systemd.io NETWORK_ONLINE](https://systemd.io/NETWORK_ONLINE/) -- After + Wants for network-online.target
- Project codebase -- pyproject.toml console_scripts, __main__.py entry point, config.py loader, run.sh patterns

### Secondary (MEDIUM confidence)
- [NixOS Type=exec discussion](https://github.com/NixOS/nixpkgs/issues/51332) -- Type=exec vs Type=simple tradeoffs
- [RPi Forums gpio-ir](https://forums.raspberrypi.com/viewtopic.php?t=205490) -- ir-keytable + gpio-ir integration patterns

### Tertiary (LOW confidence)
- ProtectSystem/ProtectHome sandbox behavior with ExecStartPre -- needs on-device testing [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- systemd on Bookworm is extremely well-documented
- Architecture: HIGH -- service unit + install script are bog-standard patterns
- Pitfalls: HIGH -- well-known systemd gotchas, verified against official docs

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (stable domain, no fast-moving dependencies)
