---
phase: 04-deployment-and-hardening
reviewed: 2026-04-11T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - install.sh
  - projector-bridge.service
  - projector-bridge.yaml.example
findings:
  critical: 0
  warning: 5
  info: 3
  total: 8
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-04-11
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Three deployment artifacts were reviewed: the install shell script, the systemd unit file, and the example YAML config. The code is generally well-structured and makes correct use of `set -euo pipefail`, systemd hardening directives, and idempotent design. However, there are two interacting issues that will cause a broken first-install experience: the service is restarted immediately after the operator is told to edit the config, and the service unit file contains a hardcoded username and absolute paths that make it non-portable. A secondary concern is that `ExecStartPre` uses a hardcoded `rc0` device name that can vary between boots.

---

## Warnings

### WR-01: Service started before operator can edit config

**File:** `install.sh:65`
**Issue:** Step 6 unconditionally runs `sudo systemctl restart "$SERVICE_NAME"` immediately after step 4 prints "Edit projector host/password in this file before starting." On a fresh install where the config was just copied from the example (with `password: ""`), the daemon starts before the operator has configured it. This will cause an immediate connection failure or authentication failure loop (restarting every 3 seconds per `RestartSec=3`). The `Restart=always` policy means the unit stays in a crash loop until someone edits the config and restarts manually.

**Fix:** On fresh install (config just created from example), skip the start step and instruct the operator to start manually after editing:

```bash
# Step 6: Start or restart the service
echo "[6/6] Starting service..."
if [ "$CONFIG_CREATED" = "true" ]; then
    echo ""
    echo "  Config was just created. Edit $CONFIG_FILE then run:"
    echo "    sudo systemctl start $SERVICE_NAME"
else
    sudo systemctl restart "$SERVICE_NAME"
    echo ""
fi
```

Set `CONFIG_CREATED=false` before step 4 and `CONFIG_CREATED=true` inside the `cp` branch at line 43.

---

### WR-02: Hardcoded username and paths in service file not substituted by install.sh

**File:** `projector-bridge.service:8-12`
**Issue:** `User=trent`, `WorkingDirectory=/home/trent/sony-projector-ip-control`, `ReadWritePaths=/home/trent/sony-projector-ip-control`, and `ExecStart=/home/trent/sony-projector-ip-control/.venv/bin/projector-bridge` are all hardcoded to user `trent`. The install script copies the file verbatim at line 59 with no variable substitution. This means any installation by a user other than `trent` (or in a different directory) produces a broken service that cannot start.

**Fix:** Either (a) perform substitution in `install.sh` before copying, or (b) use `$REPO_DIR` and `$(whoami)` during install:

```bash
# Option A: substitute during install
CURRENT_USER="$(whoami)"
sudo sed \
    -e "s|User=trent|User=$CURRENT_USER|g" \
    -e "s|/home/trent/sony-projector-ip-control|$REPO_DIR|g" \
    "$SERVICE_FILE" > "$SYSTEMD_DIR/$SERVICE_NAME.service"
```

Or (b) use `%h` (home dir) and a parameterized unit with a drop-in, but option A is simpler for this project.

---

### WR-03: ExecStartPre uses hardcoded rc0 — will break if device is enumerated differently

**File:** `projector-bridge.service:11`
**Issue:** `ExecStartPre=/usr/bin/ir-keytable -s rc0 -p sony` assumes the IR receiver is always enumerated as `rc0`. On a system with other RC devices attached, or after certain kernel updates, it may become `rc1` or another index. Since `ExecStartPre` (without a leading `-`) is a hard dependency, any failure here prevents the service from starting entirely — with an error that may not be immediately obvious.

**Fix:** Either use a leading `-` to make the failure non-fatal (so the daemon still starts and logs its own error), or make the rc device name configurable:

```ini
# Tolerate ir-keytable failure so daemon can start and report its own diagnostic
ExecStartPre=-/usr/bin/ir-keytable -s rc0 -p sony
```

Or detect the rc device in `install.sh` and write the correct index into the unit.

---

### WR-04: pip install uses editable mode (-e) in production deployment

**File:** `install.sh:37`
**Issue:** `"$VENV_DIR/bin/pip" install --quiet -e "$REPO_DIR"` installs the package in editable (development) mode. In editable mode, Python imports from the source tree directly. This is correct for development but means the `src/` directory must always be present and intact at the repo path at runtime. A regular install (`pip install .`) copies the package into the venv's `site-packages`, making it independent of the working directory and more appropriate for a production daemon.

**Fix:**
```bash
"$VENV_DIR/bin/pip" install --quiet "$REPO_DIR"
```

Note: if live-editing the source during development is desired, keep `-e` but document this as a development-only mode.

---

### WR-05: ReadWritePaths grants write access to entire repo directory

**File:** `projector-bridge.service:21`
**Issue:** `ReadWritePaths=/home/trent/sony-projector-ip-control` grants the daemon write access to the entire repository — including source code, the `.venv`, and `install.sh`. The daemon only needs to read the config file and write nothing at runtime (logging goes to journald via `StandardOutput=journal`). If the daemon process is ever compromised or has a path traversal bug, it can overwrite its own source.

**Fix:** Since the daemon appears to need no filesystem writes at runtime, remove `ReadWritePaths` entirely (the config file only needs read access under `ProtectHome=read-only`). If a runtime-writable path is needed (e.g., a PID file or socket), specify only that path:

```ini
ProtectHome=read-only
# ReadWritePaths= (remove or leave empty)
```

If the config loading code needs to resolve the path relative to the working directory, ensure it only uses `O_RDONLY`.

---

## Info

### IN-01: apt-get uses -qq which suppresses error output

**File:** `install.sh:29-30`
**Issue:** `-qq` on `apt-get` suppresses all output including errors. When combined with `set -euo pipefail`, a failed apt-get will cause the script to exit, but the operator will see no diagnostic message explaining which package failed or why.

**Fix:** Use `-q` (single quiet flag) instead to retain error output while suppressing progress noise, or log failures explicitly:

```bash
sudo apt-get update -q
sudo apt-get install -y -q ir-keytable
```

---

### IN-02: gpio-ir check silently passes on non-RPi OS (wrong boot config path)

**File:** `install.sh:20`
**Issue:** `grep -q ... /boot/firmware/config.txt 2>/dev/null` silently suppresses the check if the file doesn't exist (e.g., on a system using `/boot/config.txt` from older RPi OS). The `2>/dev/null` swallows the "no such file" error, so the check passes without warning if the path is wrong. This is low risk since the project targets Bookworm specifically (which uses `/boot/firmware/`), but worth noting.

**Fix:** Warn explicitly when the file is not found:

```bash
if [ ! -f /boot/firmware/config.txt ]; then
    echo "WARNING: /boot/firmware/config.txt not found. Cannot check gpio-ir overlay."
elif ! grep -q "dtoverlay=gpio-ir" /boot/firmware/config.txt; then
    echo "WARNING: gpio-ir overlay not found ..."
fi
```

---

### IN-03: Example config has no comment warning about empty password behavior

**File:** `projector-bridge.yaml.example:8`
**Issue:** `password: ""` has no inline comment explaining what an empty password means (unauthenticated access, or authentication will fail). Operators unfamiliar with ADCP may leave this empty and be confused by connection errors if the projector requires a password.

**Fix:** Add a comment:

```yaml
  password: ""   # Leave empty if projector has no password set; otherwise enter the projector's IP Control password
```

---

_Reviewed: 2026-04-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
