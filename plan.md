# Sony VPL-XW5000ES IR-to-ADCP Bridge + WiFi Bridge — Implementation Plan

## Context

The Sony VPL-XW5000ES projector has a nonfunctional IR receiver. The projector supports ADCP (Advanced Display Control Protocol) over TCP port 53595, which provides full remote-control capabilities via its ethernet port. A Raspberry Pi 3B will serve as: (1) an IR receiver that translates Sony SIRC remote commands into ADCP commands sent over the network, and (2) a WiFi-to-Ethernet bridge since there's no ethernet run to the projector location. Priority is IR bridge first, WiFi bridge second.

## Architecture

```
[Sony Remote] --IR--> [TSOP38238] --GPIO18--> [RPi 3B kernel gpio-ir]
    --> [evdev /dev/input/eventN] --> [Python daemon] --TCP:53595--> [Projector eth0]

[Home WiFi] --wlan0--> [RPi 3B NAT] --eth0--> [Projector]
```

## Key Technical Decisions

- **IR decoding**: Kernel `gpio-ir` overlay + `ir-keytable` (battle-tested, interrupt-driven) — NOT pigpio (unreliable userspace timing)
- **IR event reading**: Python `evdev` library reading `/dev/input/eventN` — NOT triggerhappy (avoids per-press shell spawn latency)
- **ADCP connections**: Open-per-command (connect → auth → send → close) — projector has 60s idle timeout, auth is per-connection
- **WiFi bridge**: NAT routing (true L2 bridging impossible over WiFi), dnsmasq for DHCP on eth0
- **Python async**: `asyncio` for the ADCP client and event loop

## Project Structure

```
sony-projector-ip-control/
├── README.md
├── pyproject.toml                     # deps: pyyaml, evdev
├── config.example.yaml                # IR scancode → ADCP command mapping
├── src/projector_bridge/
│   ├── __init__.py
│   ├── __main__.py                    # Entry point, argparse, asyncio loop, signal handling
│   ├── adcp_client.py                 # TCP client: connect, SHA256 auth, send command, parse response
│   ├── ir_listener.py                 # evdev-based IR event reader (auto-detect rc device)
│   ├── command_mapper.py              # Scancode → ADCP lookup, debounce/repeat logic
│   └── config.py                      # YAML config loader with dataclass validation
├── keymaps/
│   └── sony-projector.toml            # ir-keytable keymap (protocol + scancode → keycode)
├── scripts/
│   ├── install.sh                     # Full RPi deployment script
│   ├── setup-wifi-bridge.sh           # dnsmasq + iptables NAT configuration
│   └── discover-remote.sh             # Helper to discover IR scancodes
├── systemd/
│   ├── projector-bridge.service
│   └── wifi-bridge.service
└── tests/
    ├── test_adcp_client.py
    ├── test_command_mapper.py
    ├── test_config.py
    └── mock_projector.py              # Fake ADCP server for testing
```

## Implementation Phases

### Phase 1: ADCP Client (no Pi needed)
**File**: `src/projector_bridge/adcp_client.py`

- Async TCP client connecting to port 53595
- Authentication flow:
  1. Connect, read first line
  2. If "NOKEY" → no auth needed
  3. Else → compute `sha256(challenge + password).hexdigest()`, send it
  4. Read "ok" or "err_auth"
- Send command (`power "on"\r\n`), read response
- Response parsing: "ok", quoted values, error codes (err_cmd, err_val, err_option, err_inactive)
- Retry logic with configurable attempts/delay
- Reference implementations: tokyotexture/homeassistant-custom-components, kennymc-c/ucr-integration-sonyADCP

### Phase 2: Configuration System (no Pi needed)
**File**: `src/projector_bridge/config.py`

Dataclass-based config from YAML:
- `ProjectorConfig`: ip, port, password, timeout, retry settings
- `IRConfig`: device path (auto-detect), protocol (sony-15), repeat timing
- `CommandMapping`: scancode → {adcp command, description, repeat bool}
- Search: `./config.yaml` → `~/.config/projector-bridge/config.yaml` → `/etc/projector-bridge/config.yaml`

### Phase 3: Mock Projector Server (no Pi needed)
**File**: `tests/mock_projector.py`

TCP server simulating ADCP for development/testing. Sends challenge or NOKEY, validates auth, accepts commands, logs them, returns "ok".

### Phase 4: Command Mapper (no Pi needed)
**File**: `src/projector_bridge/command_mapper.py`

- Lookup scancode in config mapping
- Debounce: `repeat: false` commands only fire on key press, not hold
- Repeat: `repeat: true` commands fire on press + hold at configured rate
- Global 100ms minimum between ADCP sends (prevent projector flooding)
- Log unknown scancodes at INFO level (aids mapping new buttons)

### Phase 5: Main Application + Unit Tests (no Pi needed)
**Files**: `__main__.py`, `tests/test_*.py`

- CLI: `python -m projector_bridge [--config path] [--discover] [--log-level DEBUG]`
- `--discover` mode: print scancodes as buttons are pressed (no ADCP sends)
- Signal handling: SIGTERM/SIGINT for clean shutdown
- Unit tests against mock projector

### Phase 6: IR Keymap + Listener (needs Pi + TSOP38238)
**Files**: `keymaps/sony-projector.toml`, `src/projector_bridge/ir_listener.py`, `scripts/discover-remote.sh`

- Boot config: `dtoverlay=gpio-ir,gpio_pin=18` in `/boot/firmware/config.txt`
- ir-keytable keymap: protocol=sony, variant=sony-15, placeholder scancodes
- discover-remote.sh: runs `ir-keytable -p sony -t` for scancode discovery
- ir_listener.py: evdev reads `/dev/input/eventN`, auto-detects rc device, emits scancode + event type to callback

### Phase 7: WiFi-to-Ethernet Bridge (Pi, independent of IR work)
**File**: `scripts/setup-wifi-bridge.sh`

Network topology: wlan0 (home WiFi, DHCP from router) → NAT → eth0 (192.168.4.1/24, dnsmasq DHCP)
- Static IP on eth0: 192.168.4.1
- dnsmasq: DHCP range 192.168.4.2–192.168.4.20 on eth0
- iptables: MASQUERADE on wlan0, FORWARD eth0↔wlan0
- IP forwarding: `net.ipv4.ip_forward=1` in sysctl
- Projector gets ~192.168.4.2, config.yaml points to that IP

### Phase 8: systemd Services + Install Script (Pi, final deployment)
**Files**: `systemd/*.service`, `scripts/install.sh`

- projector-bridge.service: ExecStartPre loads ir-keytable keymap, ExecStart runs Python daemon, Group=input for /dev/input access, Restart=always
- wifi-bridge.service: oneshot, RemainAfterExit=yes
- install.sh: apt packages (ir-keytable, python3-venv, dnsmasq, iptables-persistent), create venv, deploy code/config, enable services, prompt reboot

## Hardware

**TSOP38238 wiring to RPi 3B:**
| TSOP38238 Pin | RPi Pin | Function |
|---|---|---|
| VCC (pin 3) | Pin 1 | 3.3V |
| GND (pin 1) | Pin 6 | Ground |
| Signal (pin 2) | Pin 12 | GPIO 18 |

No pull-up resistor needed (internal pull-up in TSOP38238).

## ADCP Command Reference (VPL-XW5000ES)

```
power "on"          power "off"         power_status ?
input "hdmi1"       input "hdmi2"
blank "on"          blank "off"
key "menu"          key "up"            key "down"
key "left"          key "right"         key "enter"
muting "on"         muting "off"
```

Full command list requires testing against the actual projector. Sony protocol manuals:
- https://pro.sony/s3/2018/07/03140912/Sony_Protocol-Manual_1st-Edition-Revised-2.pdf
- https://pro.sony/s3/2018/07/05140342/Sony_Protocol-Manual_Supported-Command-List_1st-Edition.pdf
- VPL-XW5000ES ADCP config: https://helpguide.sony.net/vpl/xw5000/v1/en/contents/TP1000558245.html

## Dependencies

**System (apt)**: ir-keytable, python3-pip, python3-venv, dnsmasq, iptables-persistent
**Python (pip)**: pyyaml, evdev

## Testing Strategy

1. **Unit tests** (dev machine): mock_projector.py simulates ADCP, test auth/commands/mapping/config
2. **Integration test** (Pi, no projector): mock server on localhost, real IR remote → verify full pipeline
3. **Smoke test** (Pi + projector): power on/off, input switching, menu navigation, WiFi bridge ping

## Risks

- **Unknown scancodes**: Remote's exact SIRC codes undocumented. Mitigated by discover mode.
- **SIRC bit width**: Remote may use 12, 15, or 20-bit. Kernel tries all when protocol=sony.
- **Standby connectivity**: Projector may reject ADCP in deep standby. Requires "Network Standby" enabled in projector settings.
- **XW5000ES has manual lens**: No motorized zoom/shift ADCP commands available (hardware limitation).
