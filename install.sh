#!/usr/bin/env bash
# Sony Projector IR-to-ADCP Bridge - Install Script
# Deploys all dependencies, code, config, and systemd service.
# Idempotent: safe to re-run after git pull or config changes.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"
SERVICE_NAME="projector-bridge"
SERVICE_FILE="$REPO_DIR/$SERVICE_NAME.service"
SYSTEMD_DIR="/etc/systemd/system"
CONFIG_FILE="$REPO_DIR/projector-bridge.yaml"
EXAMPLE_FILE="$REPO_DIR/projector-bridge.yaml.example"

echo "=== Sony Projector IR-to-ADCP Bridge Installer ==="
echo ""

# Step 1: Check for gpio-ir overlay (D-07: warn but don't modify boot config)
echo "[1/6] Checking gpio-ir overlay..."
if ! grep -q "dtoverlay=gpio-ir" /boot/firmware/config.txt 2>/dev/null; then
    echo "WARNING: gpio-ir overlay not found in /boot/firmware/config.txt"
    echo "  Add this line to /boot/firmware/config.txt and reboot:"
    echo "  dtoverlay=gpio-ir,gpio_pin=18"
    echo ""
fi

# Step 2: Install system dependencies
echo "[2/6] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq ir-keytable

# Step 3: Create venv and install package (idempotent)
echo "[3/6] Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --quiet -e "$REPO_DIR"

# Step 4: Deploy config (D-06: never overwrite existing config)
echo "[4/6] Checking configuration..."
if [ ! -f "$CONFIG_FILE" ]; then
    if [ -f "$EXAMPLE_FILE" ]; then
        cp "$EXAMPLE_FILE" "$CONFIG_FILE"
        chmod 600 "$CONFIG_FILE"
        echo "  Created config from example: $CONFIG_FILE"
        echo "  Edit projector host/password in this file before starting."
    else
        echo "  WARNING: No config file and no example found."
        echo "  Create projector-bridge.yaml before starting the service."
    fi
else
    echo "  Config exists: $CONFIG_FILE (not overwritten)"
    # Ensure restrictive permissions on existing config (contains password)
    chmod 600 "$CONFIG_FILE"
fi

# Step 5: Deploy systemd unit and enable service
echo "[5/6] Deploying systemd service..."
sudo cp "$SERVICE_FILE" "$SYSTEMD_DIR/"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

# Step 6: Start or restart the service
echo "[6/6] Starting service..."
sudo systemctl restart "$SERVICE_NAME"
echo ""

# Final status
echo "=== Installation Complete ==="
STATUS=$(systemctl is-active "$SERVICE_NAME" 2>/dev/null || true)
echo "Service status: $STATUS"
echo ""
echo "Useful commands:"
echo "  journalctl -u $SERVICE_NAME -f    # follow logs"
echo "  systemctl status $SERVICE_NAME    # check status"
echo "  sudo systemctl restart $SERVICE_NAME  # restart after changes"
