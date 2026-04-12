# Sony Projector IR-to-ADCP Bridge

A Python daemon running on a Raspberry Pi that restores remote control functionality to a Sony VPL-XW5000ES projector with a broken IR receiver. It receives Sony SIRC IR commands via an IR sensor and translates them into ADCP (Advanced Display Control Protocol) commands sent over TCP to the projector.

**Press a button on the Sony remote, the projector responds.**

## How It Works

```
[Sony Remote] --IR--> [KY-022 sensor] --GPIO 18--> [RPi kernel gpio-ir]
    --> [evdev /dev/input/eventN] --> [Python daemon] --TCP:53595--> [Projector]
```

The kernel's `gpio-ir` overlay decodes Sony SIRC IR signals at the interrupt level. The Python daemon reads decoded scancodes via `evdev`, maps them to ADCP commands using a YAML config, and sends them over TCP with SHA256 challenge-response authentication.

## Hardware

- **Raspberry Pi 3B** (or newer) running Raspberry Pi OS Bookworm
- **KY-022 IR receiver module** (VS1838B) — wired to GPIO 18
- **Sony VPL-XW5000ES** projector (or any Sony projector supporting ADCP)
- **Sony RM-PJ28** remote (or compatible Sony projector remote)

### Wiring

| KY-022 Pin | RPi Pin | Function |
|------------|---------|----------|
| S (Signal) | Pin 12  | GPIO 18  |
| + (VCC)    | Pin 1   | 3.3V     |
| - (GND)    | Pin 6   | Ground   |

## Quick Start (Raspberry Pi)

### Prerequisites

Add the IR overlay to `/boot/firmware/config.txt` and reboot:

```
dtoverlay=gpio-ir,gpio_pin=18
```

### Install

```bash
git clone https://github.com/trentfoley/sony-projector-ip-control.git
cd sony-projector-ip-control
bash install.sh
```

The install script:
1. Installs `ir-keytable` via apt
2. Creates a Python virtual environment
3. Installs the package
4. Copies `projector-bridge.yaml.example` to `projector-bridge.yaml` (if no config exists)
5. Deploys and enables the systemd service

### Configure

Edit `projector-bridge.yaml` with your projector's IP and password:

```yaml
projector:
  host: "192.168.1.80"    # Your projector's IP address
  port: 53595
  password: ""             # ADCP password (empty if auth disabled)
```

Then restart the service:

```bash
sudo systemctl restart projector-bridge
```

## Configuration

The config file (`projector-bridge.yaml`) has three sections:

- **projector** — Host, port, password, timeout, and retry settings
- **ir** — Input device name and IR protocol
- **mappings** — Scancode-to-ADCP command map with repeat/debounce behavior

See `projector-bridge.yaml.example` for a complete reference with all discovered scancodes for the Sony RM-PJ28 remote.

### Mapping New Remote Buttons

Use discover mode to find scancodes for unmapped buttons:

```bash
projector-bridge --discover
```

This prints raw scancodes as you press buttons without sending any ADCP commands. Add new scancodes to the `mappings` section of your config file.

## ADCP Command Reference

Common commands for the VPL-XW5000ES:

```
power "on"          power "off"         power_status ?
input "hdmi1"       input "hdmi2"
blank "on"          blank "off"
key "menu"          key "up"            key "down"
key "left"          key "right"         key "enter"
muting "on"         muting "off"
```

See the [Sony ADCP Protocol Manual](https://pro.sony/s3/2018/07/03140912/Sony_Protocol-Manual_1st-Edition-Revised-2.pdf) and [Supported Command List](https://pro.sony/s3/2018/07/05140342/Sony_Protocol-Manual_Supported-Command-List_1st-Edition.pdf) for the full command set.

## Service Management

```bash
# Check status
systemctl status projector-bridge

# Follow logs
journalctl -u projector-bridge -f

# Restart after config changes
sudo systemctl restart projector-bridge

# Stop the service
sudo systemctl stop projector-bridge
```

The service restarts automatically on crash (`Restart=always`, 3-second delay).

## Development

Development and testing work on any machine — no Pi or projector hardware required.

```bash
# Create venv and install with dev dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Run against the built-in mock ADCP server
python -m projector_bridge.mock_server &
python -m projector_bridge --config projector-bridge.yaml
```

### Project Structure

```
src/projector_bridge/
    __main__.py      # CLI entry point, async event loop, signal handling
    adcp.py          # TCP client with SHA256 auth and retry logic
    config.py        # YAML config loader with dataclass validation
    mapper.py        # Scancode-to-ADCP lookup, debounce, rate limiting
    listener.py      # evdev IR event reader with device auto-discovery
    mock_server.py   # Fake ADCP server for development and testing
```

## Adapting for Your Setup

To use this with a different Sony projector or remote:

1. **Update the projector IP/password** in `projector-bridge.yaml`
2. **Discover your remote's scancodes** — run `projector-bridge --discover` and press each button
3. **Map scancodes to ADCP commands** — add entries to the `mappings` section
4. **Update the service file** if your username or install path differs from the defaults (`projector-bridge.service` has hardcoded paths)

### Notes

- The projector must have **Network Standby** enabled in its settings, or ADCP is unreachable when powered off
- ADCP commands are blocked while the projector's OSD menu is open
- The daemon uses open-per-command TCP connections (connect, auth, send, close) since the projector has a 60-second idle timeout

## License

MIT
