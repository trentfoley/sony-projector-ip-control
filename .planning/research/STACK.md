# Technology Stack

**Project:** Sony Projector IR-to-ADCP Bridge
**Researched:** 2026-04-09

## Recommended Stack

### Runtime Environment

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Raspberry Pi OS Bookworm | Latest (kernel 6.6+) | Operating system | Current stable RPi OS; ships with NetworkManager, Python 3.11, and kernel gpio-ir support out of the box | HIGH |
| Python | 3.11.x (system) | Application runtime | Ships with Bookworm; no reason to install a newer version. 3.11 is well within support range of all dependencies | HIGH |
| venv | stdlib | Dependency isolation | Bookworm mandates virtual environments for pip installs; use `python3 -m venv` | HIGH |

### IR Reception (Kernel Layer)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| gpio-ir overlay | Kernel built-in | Hardware IR decoding | Interrupt-driven, in-kernel SIRC decoding. Replaced lirc-rpi in kernel 4.19+. Battle-tested for IR reception on RPi. Configured via `dtoverlay=gpio-ir,gpio_pin=18` in `/boot/firmware/config.txt` | HIGH |
| ir-keytable | v4l-utils package | Keymap loading + protocol config | Standard Linux tool for loading scancode-to-keycode maps onto rc devices. Supports TOML keymap format. Install via `apt install ir-keytable` | HIGH |

**Why not pigpio:** pigpio does IR decoding in userspace via polling/callbacks. On a non-realtime Linux kernel, timing jitter causes missed pulses and phantom codes. The kernel gpio-ir driver uses hardware interrupts and is immune to userspace scheduling delays. Every serious RPi IR project has moved to gpio-ir.

**Why not LIRC:** LIRC userspace daemon was the old approach. Kernel 4.19+ replaced lirc-rpi with gpio-ir, moving decoding into kernel space. LIRC is now unnecessary overhead for receive-only use cases -- the kernel rc subsystem handles protocol decoding natively.

### Python Dependencies (Runtime)

| Library | Version | Purpose | Why | Confidence |
|---------|---------|---------|-----|------------|
| evdev | >=1.9.0 | Read IR input events | Direct Python bindings to Linux input subsystem. `async_read_loop()` integrates natively with asyncio. No subprocess spawning, no parsing -- just typed event objects. Requires Python >=3.9 | HIGH |
| PyYAML | >=6.0.2 | Parse config file | Mature, widely-used YAML parser. `yaml.safe_load()` is sufficient. No need for ruamel.yaml or other alternatives for this simple config format | HIGH |

**Why not triggerhappy:** triggerhappy (thd) is a hotkey daemon that spawns shell commands per keypress. For an IR bridge that needs sub-100ms latency and repeat/debounce logic, spawning a shell per press is unacceptable. evdev gives in-process event delivery with asyncio integration. Also, triggerhappy has known segfault bugs (thd-socket, th-cmd crashes reported in forums).

**Why not a YAML-to-dataclass library (yamldataclassconfig, heracless):** Adding a dependency for what is 15 lines of code (`yaml.safe_load()` + manual dataclass construction) is unnecessary. This project has exactly one small config file. Keep it simple.

### Python Dependencies (Dev Only)

| Library | Version | Purpose | Why | Confidence |
|---------|---------|---------|-----|------------|
| pytest | >=8.4.0 | Test runner | Industry standard. Use 8.x series (not 9.x) because 9.0 requires Python >=3.10 and we want compatibility with 3.11 (which works with both). 8.4.x is the latest 8.x line | HIGH |
| pytest-asyncio | >=1.3.0 | Async test support | Required for testing asyncio TCP client and evdev listener. Use `asyncio_mode = "auto"` in pyproject.toml to avoid decorating every test | HIGH |
| ruff | >=0.15.0 | Linter + formatter | Replaces flake8, black, isort in a single Rust-based tool. 10-100x faster. Configured in pyproject.toml. Current version 0.15.10 | MEDIUM |

**Note on pytest version:** pytest 9.0 dropped Python 3.9 support (requires >=3.10). Python 3.11 on Bookworm IS compatible with pytest 9.x, so either 8.x or 9.x works. Recommend pinning `>=8.4` to avoid surprises.

### Standard Library (No Install Needed)

| Module | Purpose | Notes |
|--------|---------|-------|
| asyncio | Event loop, TCP client, task management | Core of the daemon architecture. `asyncio.open_connection()` for ADCP TCP, `async_read_loop()` integration with evdev |
| hashlib | SHA256 challenge-response auth | `hashlib.sha256((challenge + password).encode()).hexdigest()` -- one line |
| dataclasses | Config schema | `@dataclass` for `ProjectorConfig`, `IRConfig`, `CommandMapping` |
| logging | Structured logging | Standard Python logging with configurable levels |
| signal | Graceful shutdown | SIGTERM/SIGINT handlers for clean asyncio shutdown |
| pathlib | File path handling | For config file search across multiple locations |
| argparse | CLI argument parsing | `--config`, `--discover`, `--log-level` flags |

### WiFi Bridge (System Packages)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| NetworkManager (nmcli) | System default | NAT + DHCP on eth0 | Bookworm ships with NetworkManager. `nmcli con modify "Wired connection 1" ipv4.method shared` auto-configures NAT, DHCP, and DNS forwarding in one command. No manual iptables or dnsmasq config needed | HIGH |
| iptables-persistent | apt package | Persist firewall rules | Only needed if customizing beyond what `ipv4.method shared` provides (e.g., specific subnet). NetworkManager's shared mode handles the common case | MEDIUM |
| dnsmasq | apt package | DHCP/DNS server | NetworkManager uses dnsmasq internally when `ipv4.method shared` is set. May need explicit install if not pulled as a dependency. Fallback: configure manually if NetworkManager's defaults (10.42.0.0/24) don't work and you need 192.168.4.0/24 | MEDIUM |

**Recommended approach:** Try `nmcli con modify` first. If the default 10.42.0.0/24 subnet is fine, you're done in two commands. If you need 192.168.4.0/24 specifically, either override via `ipv4.addresses 192.168.4.1/24` or fall back to manual dnsmasq + iptables.

### Build & Packaging

| Technology | Purpose | Why | Confidence |
|------------|---------|-----|------------|
| pyproject.toml | Project metadata + deps | PEP 621 standard. Single file for project config, dependencies, pytest settings, ruff settings. No setup.py, setup.cfg, or requirements.txt needed | HIGH |
| setuptools >=61.0 | Build backend | Default, well-understood, zero-config for pure Python packages. Alternatives (hatch, flit, poetry) add complexity with no benefit for a single-daemon project | HIGH |

### Deployment

| Technology | Purpose | Why | Confidence |
|------------|---------|-----|------------|
| systemd | Service management | Native on Bookworm. `Restart=always`, `After=network-online.target`, `Group=input` for /dev/input access. ExecStartPre for ir-keytable keymap loading | HIGH |
| install.sh | One-shot deployment | Shell script: apt install, venv create, config deploy, systemd enable. Idempotent for re-runs | HIGH |

## What NOT to Use

| Technology | Why Not |
|------------|---------|
| pigpio | Userspace IR decoding is unreliable on non-RT kernel. Timing jitter causes phantom/missed codes |
| LIRC (lircd) | Deprecated for receive-only. Kernel rc subsystem does protocol decoding natively since kernel 4.19 |
| triggerhappy | Shell spawn per keypress = unacceptable latency for IR bridge. Known segfault bugs |
| RPi.GPIO | Low-level GPIO library. You'd have to implement SIRC pulse-width decoding yourself. The kernel already does this |
| Flask/FastAPI | No web UI needed. The remote control IS the interface. Adding HTTP adds attack surface and complexity |
| Docker | Overkill for a single daemon on dedicated hardware. systemd + venv is simpler and more appropriate |
| MQTT/Home Assistant | Explicitly out of scope. Standalone daemon only |
| Poetry/Hatch/PDM | No benefit over setuptools for a single pure-Python package with 2 runtime dependencies |
| pydantic | Config validation overkill. dataclasses + manual validation is sufficient for a ~30-field config |
| ruamel.yaml | No need for YAML round-tripping or comments preservation. `yaml.safe_load()` is sufficient |

## Installation Commands

```bash
# System packages (on Raspberry Pi)
sudo apt update
sudo apt install -y ir-keytable python3-venv

# Optional: only if manual WiFi bridge setup needed
sudo apt install -y dnsmasq iptables-persistent

# Python virtual environment
python3 -m venv /opt/projector-bridge/venv
source /opt/projector-bridge/venv/bin/activate

# Runtime dependencies
pip install evdev pyyaml

# Dev dependencies (development machine only)
pip install pytest pytest-asyncio ruff
```

## pyproject.toml Skeleton

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "projector-bridge"
version = "0.1.0"
description = "IR-to-ADCP bridge for Sony projectors"
requires-python = ">=3.11"
dependencies = [
    "evdev>=1.9.0",
    "pyyaml>=6.0.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.4",
    "pytest-asyncio>=1.3.0",
    "ruff>=0.15.0",
]

[project.scripts]
projector-bridge = "projector_bridge.__main__:main"

[tool.pytest.ini_options]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
```

## Sources

- [evdev on PyPI](https://pypi.org/project/evdev/) -- v1.9.3, Feb 2026, Python >=3.9
- [PyYAML on PyPI](https://pypi.org/project/PyYAML/) -- v6.0.3, Sep 2025, Python >=3.8
- [pytest on PyPI](https://pypi.org/project/pytest/) -- v9.0.3, Apr 2026, Python >=3.10
- [pytest-asyncio on PyPI](https://pypi.org/project/pytest-asyncio/) -- v1.3.0, Nov 2025, Python >=3.10
- [ruff on PyPI](https://pypi.org/project/ruff/) -- v0.15.10, Apr 2026, Python >=3.7
- [python-evdev tutorial](https://python-evdev.readthedocs.io/en/latest/tutorial.html) -- async_read_loop() API
- [Raspberry Pi OS Bookworm](https://www.raspberrypi.com/software/operating-systems/) -- Python 3.11, NetworkManager, kernel 6.6+
- [RPi gpio-ir overlay](https://forums.raspberrypi.com/viewtopic.php?t=205490) -- community discussion on kernel IR
- [nmcli shared mode](https://www.cybercloudai.tech/how-to-set-up-your-raspberry-pi-as-a-wifi-bridge/) -- NetworkManager NAT bridge
- [Jeff Geerling: nmcli on Bookworm](https://www.jeffgeerling.com/blog/2023/nmcli-wifi-on-raspberry-pi-os-12-bookworm/) -- NetworkManager reference
