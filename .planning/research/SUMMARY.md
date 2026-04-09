# Project Research Summary

**Project:** Sony Projector IR-to-ADCP Bridge
**Domain:** Embedded daemon / IR-to-IP protocol bridge on Raspberry Pi
**Researched:** 2026-04-09
**Confidence:** HIGH

## Executive Summary

This project is a single-purpose embedded daemon that receives Sony SIRC infrared commands from a TSOP38238 sensor on a Raspberry Pi 3B and translates them into ADCP commands sent over TCP to a Sony VPL-XW5000ES projector whose IR receiver is broken. A secondary function is WiFi-to-Ethernet NAT bridging so the Pi (connected to home WiFi) can reach the projector (connected via Ethernet) without a dedicated cable run. The domain is well-understood: Linux kernel IR reception is mature (gpio-ir overlay + ir-keytable), the ADCP protocol is simple ASCII over TCP with SHA256 auth, and multiple open-source reference implementations exist.

The recommended approach is a pure-Python asyncio daemon with only two runtime dependencies (evdev for input events, PyYAML for config). The kernel handles all IR protocol decoding; the Python layer reads evdev events, maps scancodes to ADCP commands via a YAML config, and sends them over TCP with open-per-command connections. The architecture is a linear pipeline (IR Listener -> Command Mapper -> ADCP Client) wired by async callbacks, with no web UI, no persistent connections, and no smart-home integration. Everything that can be tested without hardware should be built first.

The key risks are: (1) Sony SIRC scancode format confusion across tools and documentation -- mitigated by a mandatory discover mode that captures codes directly from the remote, (2) ADCP authentication misimplementation -- mitigated by developing with auth disabled first and testing against a mock server, (3) projector unreachable in deep standby -- mitigated by documenting the "Network Standby" prerequisite, and (4) IR repeat flooding the projector -- mitigated by per-command debounce/throttle as core business logic, not an afterthought. SD card corruption from power loss is the primary long-term reliability concern, addressed by read-only root filesystem in the deployment phase.
## Key Findings

### Recommended Stack

The stack is minimal by design. The kernel does the heavy lifting for IR decoding; Python is the glue. Two runtime pip packages, zero web frameworks, zero databases.

**Core technologies:**
- **Raspberry Pi OS Bookworm (kernel 6.6+):** Ships with NetworkManager, Python 3.11, and gpio-ir kernel support. No custom kernel needed.
- **gpio-ir kernel overlay + ir-keytable:** Interrupt-driven IR decoding in kernel space. Replaces unreliable userspace approaches (pigpio, LIRC).
- **Python 3.11 + asyncio:** System Python on Bookworm. asyncio is the natural fit -- evdev has native async support, TCP is stdlib asyncio.
- **evdev (>=1.9.0):** Direct Python bindings to Linux input subsystem. async_read_loop() for zero-CPU-at-idle event waiting.
- **PyYAML (>=6.0.2):** Config parsing. yaml.safe_load() is the entire integration.
- **systemd:** Service management, auto-restart, ir-keytable keymap loading via ExecStartPre.
- **NetworkManager (nmcli):** WiFi-to-Ethernet NAT bridge. ipv4.method shared handles NAT + DHCP in one command.

**What NOT to use:** pigpio (unreliable userspace IR), LIRC (deprecated), triggerhappy (shells out per keypress), Flask/FastAPI (no web UI needed), Docker (overkill), Home Assistant integration (out of scope), pydantic (overkill for ~30-field config), Poetry/Hatch (no benefit over setuptools for 2-dep project).

### Expected Features

**Must have (table stakes):**
- Power on/off, input switching (HDMI 1/2), menu navigation (up/down/left/right/enter/back), blanking/muting
- SHA256 challenge-response authentication (default password: "Projector")
- Debounce for one-shot commands (power, input) and repeat support for held buttons (menu nav, brightness)
- Configurable scancode-to-ADCP mapping via YAML with per-command repeat flag
- Discover mode (--discover) for learning unknown remote scancodes
- Auto-detect IR input device by name ("gpio_ir_recv"), not hardcoded path
- WiFi-to-Ethernet NAT bridge (wlan0 -> eth0)
- Auto-start on boot via systemd with Restart=always

**Should have (differentiators for reliability):**
- Connection error logging with retry (2-3 attempts, 200ms backoff)
- ADCP response validation and typed error code handling (err_auth, err_cmd, err_val, err_inactive)
- Unknown scancode logging at INFO level (passive discovery during normal use)
- Mock ADCP server for development/testing (~100 lines, enables full pipeline TDD)
- Graceful shutdown on SIGTERM/SIGINT (close TCP, release evdev device)
- Hardware watchdog integration (dtparam=watchdog=on, WatchdogSec=10, sd_notify)

**Defer (add after real-world use reveals the need):**
- Config reload without restart (restarts take <2s, mapping changes rare after setup)
- Structured JSON logging (add when log parsing becomes a diagnosed problem)
- Additional remote button mappings for picture preset/aspect/motionflow (just YAML entries, zero code change)

**Anti-features (explicitly do NOT build):**
- Web UI or REST API (the remote IS the interface)
- Home Assistant / smart home integration (existing integrations cover this)
- Multi-projector support (two projectors = two Pis)
- Persistent/keepalive ADCP connection (projector has 60s timeout, per-connection auth)
- IR transmitting/blasting (receive only)
- OTA update mechanism (SSH + git pull)
- Projector status polling/dashboard (use RM-PJ28 INFO button)
- Volume control (XW5000ES has no speaker/volume ADCP commands)
### Architecture Approach

The architecture is a unidirectional pipeline: IR hardware -> kernel decode -> evdev events -> Python daemon (listen -> map -> send) -> projector TCP. Components are wired by async callbacks, not class hierarchies. Each component is independently testable. The open-per-command ADCP model (connect, auth, send, close) is simpler and more reliable than persistent connections given the projector 60-second idle timeout and per-connection auth requirement. All ADCP commands must be serialized through an async lock to prevent concurrent connections, since the projector likely accepts only one TCP session at a time. Total software latency from button press to ADCP send is approximately 25ms; perceptible latency is dominated by the projector response time.

**Major components:**
1. **Config Loader (config.py)** -- Parse YAML, validate, return typed dataclasses (ProjectorConfig, IRConfig, CommandMapping). Cascading file search: ./config.yaml -> ~/.config/ -> /etc/.
2. **ADCP Client (adcp_client.py)** -- TCP connect with asyncio.wait_for(timeout=5s), SHA256 auth or NOKEY, send command, parse response, close. Retry with backoff for transient errors. Never retry auth or command errors.
3. **Command Mapper (command_mapper.py)** -- Scancode lookup, per-command debounce (one-shot vs. repeatable), global rate limit (100ms floor), unknown scancode logging.
4. **IR Listener (ir_listener.py)** -- Auto-detect gpio_ir_recv device via InputDevice.list_devices(). Read EV_MSC/MSC_SCAN for stable scancodes (not EV_KEY keycodes). async_read_loop for zero-CPU idle.
5. **Main Daemon (__main__.py)** -- CLI args (--discover, --config, --log-level), asyncio loop, SIGTERM/SIGINT handlers, component wiring via callbacks.
6. **Mock ADCP Server (mock_projector.py)** -- TCP server: send challenge or NOKEY, validate auth, accept commands, return "ok", log everything. ~100 lines.
7. **WiFi Bridge (setup-wifi-bridge.sh)** -- NAT, DHCP, IP forwarding. Independent of IR bridge code.

### Critical Pitfalls

1. **Sony SIRC scancode format confusion** -- Scancodes differ across tools (kernel vs Arduino vs LIRC vs community databases). The kernel reassembles bits with device address in upper bits, function in lower bits. Prevention: ONLY use discover mode output as source of truth. Never copy scancodes from the internet. Force a specific protocol variant in ir-keytable.
2. **ADCP auth misimplementation** -- Concatenation order is challenge+password (not password+challenge), result must be lowercase hex digest, must handle both NOKEY and challenge paths. Prevention: develop with auth disabled first, use kennymc-c reference implementation, unit test the hash with known vectors, use Wireshark to verify.
3. **Projector unreachable in deep standby** -- "Network Standby" / "Standby Mode: Standard" must be enabled or the projector network stack powers off entirely. Prevention: document prominently as a prerequisite, verify during initial setup, handle ConnectionRefused with specific error message referencing Network Standby.
4. **IR repeat flooding** -- Held buttons generate 8 events/sec via evdev, each requiring connect+auth+send+close. Commands queue faster than they send, causing growing backlog and erratic projector behavior. Prevention: per-command-type debounce/throttle with key-state filtering (down=1 send, repeat=2 rate-limit or suppress, up=0 ignore). Serialize through async lock.
5. **SD card corruption from power loss** -- SD cards have no power-loss protection. Prevention: read-only root filesystem (overlayfs via raspi-config), logs to tmpfs (journald Storage=volatile), fsck.repair=yes on boot.
6. **WiFi drops kill SSH access** -- RPi 3B BCM43438 WiFi has known firmware issues, aggressive power saving. Prevention: disable power management (wifi.powersave=2), deploy gateway-ping watchdog. Note: IR bridge uses eth0 and is unaffected by WiFi drops.
## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Project Foundation and Config System
**Rationale:** Every component depends on configuration. The config schema defines the YAML format, projector connection settings, and command mapping structure. Starting here means all subsequent phases have a stable contract to code against.
**Delivers:** pyproject.toml, project structure, Config dataclasses, YAML loader with cascading file search, config validation.
**Addresses:** Configurable scancode-to-command mapping (FEATURES), Config Loader component (ARCHITECTURE).
**Avoids:** No pitfalls at this stage -- pure software, no hardware dependencies.

### Phase 2: ADCP Client and Mock Server
**Rationale:** The ADCP client is the most critical component -- if it cannot talk to the projector, nothing works. Building the mock server alongside it enables full test coverage without hardware. Auth is the hardest part and must be nailed before anything else.
**Delivers:** ADCP TCP client with SHA256 auth, retry logic, error code handling. Mock ADCP server for testing. Unit tests for auth flow.
**Addresses:** SHA256 auth, connection retry, ADCP response validation (FEATURES). ADCP Client component (ARCHITECTURE).
**Avoids:** Auth misimplementation (Pitfall 2) by developing with NOKEY first, then layering in auth. Connection timeout races (Pitfall 8) by designing async serialization from day one.

### Phase 3: Command Mapper with Debounce/Repeat
**Rationale:** The translation layer between IR events and ADCP commands. Debounce and repeat handling is core business logic that determines whether the bridge feels responsive or broken. Depends on config (Phase 1) and ADCP client (Phase 2).
**Delivers:** Scancode-to-ADCP lookup, per-command debounce (one-shot vs. repeatable), rate limiting, unknown scancode logging.
**Addresses:** Debounce/repeat support, unknown scancode logging (FEATURES). Command Mapper component (ARCHITECTURE).
**Avoids:** IR repeat flooding (Pitfall 4) by making throttle/debounce first-class concerns.

### Phase 4: Main Application and Discover Mode
**Rationale:** Wires everything together. Discover mode is the bootstrap mechanism -- without it, users cannot create their scancode mapping. At this point the full pipeline is testable on any dev machine against the mock server.
**Delivers:** CLI entry point with --discover and --config flags, asyncio event loop, signal handling (SIGTERM/SIGINT), graceful shutdown. Full pipeline test (mock IR events -> mapper -> mock ADCP server).
**Addresses:** Discover mode, graceful shutdown (FEATURES). Main Daemon component (ARCHITECTURE).
**Avoids:** No hardware-specific pitfalls. Completes the "works on dev machine" milestone.

### Phase 5: IR Listener and Hardware Integration
**Rationale:** First phase requiring the Raspberry Pi and TSOP38238 hardware. gpio-ir overlay config, ir-keytable keymap loading, evdev device auto-detection. Deliberately pushed late so all software is proven before hardware enters the picture.
**Delivers:** gpio-ir overlay configuration, ir-keytable TOML keymap, evdev-based IR listener with device auto-detection, end-to-end test with real remote.
**Addresses:** Auto-detect IR input device (FEATURES). IR Listener component (ARCHITECTURE).
**Avoids:** gpio-ir overlay not loading (Pitfall 7) by validating with ir-keytable -t first. Scancode format confusion (Pitfall 1) by using discover mode exclusively. Device path changes (Pitfall 9) by discovering device by name.

### Phase 6: WiFi-to-Ethernet NAT Bridge
**Rationale:** Independent of IR bridge code. Testing requires the Pi hardware. Prerequisite for the projector being network-reachable in the final installation.
**Delivers:** NetworkManager-based NAT bridge (wlan0 -> eth0), DHCP on eth0 subnet, WiFi power management disabled, connectivity watchdog.
**Addresses:** WiFi-to-Ethernet NAT bridge (FEATURES).
**Avoids:** dnsmasq boot race (Pitfall 10) with bind-dynamic. iptables not persisting (Pitfall 11) with iptables-persistent. WiFi drops (Pitfall 5) with power management disabled + watchdog.

### Phase 7: Deployment and Hardening
**Rationale:** Final phase. Makes the system production-ready for unattended ceiling-mounted operation.
**Delivers:** systemd service files (with ExecStartPre for ir-keytable), install.sh script, read-only root filesystem (overlayfs), logs to tmpfs, documentation (setup guide, Network Standby requirement, recovery procedures).
**Addresses:** Auto-start on boot, hardware watchdog (FEATURES). systemd + deployment (ARCHITECTURE).
**Avoids:** SD card corruption (Pitfall 6) with read-only rootfs. Permissions issues (Pitfall 13) by testing as systemd service. Projector unreachable in standby (Pitfall 3) documented prominently.
### Phase Ordering Rationale

- **Dependency-driven:** Config -> ADCP Client -> Mapper -> App -> IR Listener follows the data flow in reverse, ensuring each layer has its dependencies ready.
- **Hardware-deferred:** Phases 1-4 require no Pi hardware and can be developed/tested on any machine. This maximizes development velocity and enables CI.
- **WiFi bridge is independent:** It shares no code with the IR bridge and can be done whenever Pi access is available.
- **Deployment is last:** Hardening (read-only rootfs, watchdog) should wrap a working system, not be developed alongside unstable code.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (ADCP Client):** The SHA256 auth flow has subtle details (concatenation order, NOKEY vs challenge detection, error codes). The kennymc-c implementation is the best reference but is in a different language. Worth a focused research pass to extract exact protocol bytes.
- **Phase 5 (IR Listener):** Sony SIRC scancode format varies by protocol variant (12/15/20-bit). The RM-PJ28 remote exact variant and scancodes are undocumented. Needs hands-on discover mode testing.
- **Phase 6 (WiFi Bridge):** NetworkManager ipv4.method shared behavior on Bookworm may have edge cases. The default 10.42.0.0/24 subnet vs. custom 192.168.4.0/24 needs validation on-device.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Config):** Standard Python dataclasses + PyYAML. Well-documented, no surprises.
- **Phase 3 (Command Mapper):** Pure logic layer. Debounce/throttle is straightforward timer-based code.
- **Phase 4 (Main App):** Standard asyncio application wiring. CLI args via argparse.
- **Phase 7 (Deployment):** systemd service files and install scripts are well-documented patterns. Read-only rootfs via raspi-config is a known procedure.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All libraries verified on PyPI with current versions. evdev 1.9.3, PyYAML 6.0.3, pytest 8.4+. All compatible with Python 3.11 on Bookworm. |
| Features | HIGH | Feature set derived from RM-PJ28 button inventory, Sony ADCP command reference, and multiple open-source implementations. Anti-features well-reasoned. |
| Architecture | HIGH | Single-process asyncio pipeline is the standard pattern for event-driven bridges. evdev async API verified in official docs. |
| Pitfalls | HIGH | Critical pitfalls sourced from community forums with real RPi IR projects, Sony ADCP troubleshooting threads, and known RPi 3B hardware issues. |

**Overall confidence:** HIGH

The domain is well-trodden. Kernel IR support is mature, ADCP is a simple protocol, and reference implementations exist. The main uncertainty is the RM-PJ28 remote exact SIRC scancodes, which can only be resolved empirically with the actual hardware (discover mode).

### Gaps to Address

- **RM-PJ28 scancode values:** Completely undocumented. Must be discovered empirically with the actual remote during Phase 5. This is expected and the architecture accounts for it via discover mode.
- **ADCP command completeness:** The Sony protocol manual lists commands generically. Which specific commands the VPL-XW5000ES supports needs validation against the actual projector. The kennymc-c implementation is the best proxy.
- **NetworkManager shared mode subnet customization:** Whether ipv4.method shared can be overridden to use 192.168.4.0/24 instead of default 10.42.0.0/24 needs on-device validation. Fallback is manual dnsmasq config.
- **RPi 3B WiFi reliability at installation location:** Signal strength can only be assessed in-situ. May need USB WiFi dongle with external antenna.
## Sources

### Primary (HIGH confidence)
- [Sony VPL-XW5000ES Help Guide](https://helpguide.sony.net/vpl/xw5000/v1/en/contents/TP1000558245.html) -- ADCP settings, port, auth
- [Sony ADCP Protocol Manual](https://pro.sony/s3/2018/07/03140912/Sony_Protocol-Manual_1st-Edition-Revised-2.pdf) -- connection flow, command format
- [kennymc-c/ucr-integration-sonyADCP](https://github.com/kennymc-c/ucr-integration-sonyADCP) -- most complete open-source SHA256 auth implementation
- [python-evdev documentation](https://python-evdev.readthedocs.io/en/latest/tutorial.html) -- async_read_loop API, device discovery
- [Linux kernel RC-core docs](https://docs.kernel.org/driver-api/media/rc-core.html) -- kernel IR architecture
- [Raspberry Pi OS Bookworm](https://www.raspberrypi.com/software/operating-systems/) -- Python 3.11, NetworkManager, kernel 6.6+
- [ir-keytable rc_keymap(5)](https://manpages.debian.org/testing/ir-keytable/rc_keymap.5.en.html) -- TOML keymap format

### Secondary (MEDIUM confidence)
- [SB-Projects Sony SIRC Protocol](https://www.sbprojects.net/knowledge/ir/sirc.php) -- SIRC timing, 12/15/20-bit variants
- [tokyotexture/homeassistant-custom-components](https://github.com/tokyotexture/homeassistant-custom-components) -- simpler ADCP reference
- [Home Assistant Sony ADCP Control Thread](https://community.home-assistant.io/t/sony-projector-adcp-control/933745) -- real-world error patterns
- [RPi gpio-ir forum thread](https://forums.raspberrypi.com/viewtopic.php?t=205490) -- community experience with gpio-ir overlay
- [Jeff Geerling: nmcli on Bookworm](https://www.jeffgeerling.com/blog/2023/nmcli-wifi-on-raspberry-pi-os-12-bookworm/) -- NetworkManager reference

### Tertiary (LOW confidence)
- [hifi-remote.com Sony codes](https://www.hifi-remote.com/sony/) -- scancode databases (do NOT use as source of truth, format differs from kernel)
- [RPi WiFi stability threads](https://forums.raspberrypi.com/viewtopic.php?t=373043) -- anecdotal but consistent reports of BCM43438 issues

---
*Research completed: 2026-04-09*
*Ready for roadmap: yes*
