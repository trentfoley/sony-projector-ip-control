# Feature Landscape

**Domain:** IR-to-ADCP projector control bridge (embedded daemon on Raspberry Pi)
**Researched:** 2026-04-09

## Table Stakes

Features users expect. Missing = the bridge is useless or unreliable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Power on/off via remote | The single most common projector operation. Without this, the bridge serves no purpose. | Low | ADCP: `power "on"`, `power "off"`. Projector must have "Network Standby" enabled or it rejects ADCP in deep standby. |
| Input switching (HDMI 1/2) | XW5000ES has two HDMI inputs. Switching between them is a per-session action. | Low | ADCP: `input "hdmi1"`, `input "hdmi2"`. Maps to INPUT button on RM-PJ28. |
| Menu navigation (up/down/left/right/enter/back) | Required to change any projector setting. Without menu nav, the user must walk to the projector to adjust settings. | Low | ADCP: `key "menu"`, `key "up"`, `key "down"`, `key "left"`, `key "right"`, `key "enter"`. Six commands, all the same pattern. |
| Blanking/muting | Standard projector remote function. "Blank" temporarily hides the image without powering off (e.g., during intermission). | Low | ADCP: `blank "on"`, `blank "off"` or `muting "on"`, `muting "off"`. |
| Debounce on non-repeating commands | Sony SIRC retransmits frames every 45ms while a button is held. Without debounce, a single power press sends 5-10 power toggles. Kernel RC-core defaults: REP_DELAY=500ms, REP_PERIOD=125ms. | Medium | Must distinguish "press once" (power, input, menu) from "hold to repeat" (brightness +/-). Per-command `repeat: true/false` flag in YAML config. |
| Repeat support for held buttons | Brightness/contrast/sharpness adjustment buttons on the RM-PJ28 are designed to be held, generating a stream of increments. Without repeat passthrough, the user must press 40 times instead of holding. | Medium | Rate-limit repeats to prevent projector flooding. Global 100ms minimum between ADCP sends is a sensible floor. |
| SHA256 challenge-response auth | ADCP authentication is enabled by default on the XW5000ES (password: "Projector", case-sensitive). The bridge must complete auth or it cannot send any commands. | Medium | Connect, read challenge, compute `sha256(challenge + password).hexdigest()`, send it. Also handle NOKEY (auth disabled). Well-documented in kennymc-c implementation. |
| Configurable scancode-to-command mapping | Sony SIRC scancodes for the RM-PJ28 are undocumented. Remote may use 12-bit, 15-bit, or 20-bit SIRC variants. Hardcoded mappings would break for anyone with a different remote or SIRC variant. | Medium | YAML config file: scancode -> {adcp_command, repeat_bool, description}. Config search: `./config.yaml` -> `~/.config/` -> `/etc/`. |
| Discover mode | Without a way to learn scancodes from an unknown remote, the user cannot create the mapping file. This is the bootstrap mechanism for the entire system. | Low | CLI flag `--discover` that prints raw scancodes as buttons are pressed. No ADCP sends. |
| Auto-start on boot | The Pi is ceiling-mounted next to the projector. It must work unattended after power loss. No SSH should be required. | Low | systemd service with `Restart=always`, `RestartSec=3`. ExecStartPre loads ir-keytable keymap. |
| WiFi-to-Ethernet NAT bridge | The projector has only ethernet; no ethernet run exists to the projector location. Without this, the Pi cannot reach the projector over the network. | Medium | NAT routing: wlan0 (home WiFi) -> eth0 (192.168.4.0/24 subnet). dnsmasq for DHCP. iptables MASQUERADE. Infrastructure, not user-facing, but table stakes for this installation. |

## Differentiators

Features that improve reliability and usability beyond "it works." Not strictly required, but the difference between a fragile hack and a reliable appliance.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Connection error logging with retry | ADCP over TCP can fail (projector in standby, network glitch, auth failure). Logging specific ADCP error codes (`err_auth`, `err_cmd`, `err_val`, `err_inactive`) helps diagnose problems without SSH. Retry with backoff avoids a single dropped packet causing a missed command. | Low | 2-3 retries with 200ms backoff. Log at WARNING for retries, ERROR for final failure. |
| Auto-detect IR input device | The evdev device path (`/dev/input/eventN`) changes across reboots depending on USB probe order and kernel module loading. Hardcoding breaks unpredictably. | Low | Scan `/dev/input/` for devices matching "gpio_ir_recv" name. Fall back to config override if specified. |
| ADCP response validation | ADCP commands return structured responses: `"ok"`, quoted values for queries (`power_status ?` -> `"standby"`), and typed errors. Parsing these lets the bridge verify commands took effect and log meaningful diagnostics. | Low | Parse return values and error codes. Log discrepancies (sent power on, got `err_inactive` = projector in deep standby). |
| Unknown scancode logging | When a button has no mapping, log its scancode at INFO level. Turns normal use into passive discovery -- user presses unmapped buttons during viewing, log reveals their scancodes for later mapping. | Low | Zero additional complexity beyond the mapper's lookup-miss path. |
| Mock ADCP server for development | Enables full pipeline testing on any dev machine without the projector. Critical for TDD, CI, and anyone contributing who does not own an XW5000ES. | Low | TCP server: send challenge or NOKEY, validate auth, accept commands, return "ok", log everything. ~100 lines. |
| Graceful shutdown on SIGTERM/SIGINT | Clean resource release prevents stale TCP connections and partial evdev reads on service restart. | Low | asyncio signal handlers. Close any open TCP socket, release evdev device. |
| Structured logging (JSON option) | If the daemon runs headlessly for months, structured logs are easier to parse than free-text when diagnosing a problem that happened days ago. | Low | Python `logging` with optional JSON formatter via `--log-format json`. Default: human-readable. |
| Picture preset / aspect ratio / motionflow buttons | The RM-PJ28 has dedicated buttons for CALIBRATED PRESET, ASPECT, and MOTIONFLOW. Mapping these provides one-button switching for common picture adjustments. | Low | Just more YAML entries using the same mapping mechanism. Zero code change required beyond discovering the scancodes. |
| Hardware watchdog integration | The RPi 3B has a hardware watchdog (15s max timeout). If the daemon hangs (not crashes -- e.g., deadlocked asyncio loop), systemd `Restart=always` will NOT help. The hardware watchdog reboots the Pi. | Medium | Enable `dtparam=watchdog=on`, set `WatchdogSec=10` in the service file, send `sd_notify("WATCHDOG=1")` periodically from the asyncio loop. |
| Config file reload without restart | Allows adding new button mappings discovered during use without restarting the service. | Medium | Handle SIGHUP to re-parse YAML and swap the mapping dictionary. Or watch with inotify. Service restart takes <2s anyway, so this is a convenience. |

## Anti-Features

Features to explicitly NOT build. These are scope traps that add complexity without proportional value for this single-purpose appliance.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Web UI or REST API | The physical remote IS the interface. A web UI duplicates its function and adds a web server, auth, CORS, frontend -- massive scope for a headless ceiling-mounted Pi. The UCR and HA integrations already exist for app-based control. | Use the Sony remote. Point users to existing HA/UCR integrations for app control. |
| Home Assistant / smart home integration | Out of scope per PROJECT.md. Two existing HA integrations cover this (tokyotexture, kennymc-c). Duplicating their work ties the bridge to HA's release cycle. | Keep standalone. Reference existing integrations in README. |
| Multi-projector support | Single projector, single Pi, single remote. Multi-projector adds routing logic (which remote -> which projector), connection management, and testing matrix for zero current users. | If someone has two projectors, they run two Pis with two configs. |
| Motorized lens control | The VPL-XW5000ES has a manual lens. There are no ADCP commands for lens zoom/shift/focus on this model. Implementing lens commands that cannot work is misleading. | Document the hardware limitation. The YAML mapping system lets users with motorized-lens projectors add those commands themselves. |
| Persistent/keepalive ADCP connection | The projector has a 60-second idle timeout and requires auth per connection. A persistent connection adds keepalive pings, reconnection logic, and session state management -- to save ~50ms of overhead the user never notices. | Open-per-command: connect, auth, send, close. Simple, stateless, matches projector's design. |
| IR transmitting (blasting) | This bridge receives IR and sends ADCP. IR transmit requires an IR LED + transistor driver circuit and changes the architecture from unidirectional to bidirectional. | Keep unidirectional: IR in, ADCP out. |
| OTA firmware/update mechanism | Over-engineering for a single-device deployment. The Pi runs standard Linux. | SSH + git pull + systemctl restart. Or re-run install.sh. |
| Projector status polling/dashboard | Periodically querying lamp hours, temperature, error state adds network traffic and complexity for info only useful during troubleshooting. The RM-PJ28 INFO button shows this on the projected image. | One-shot ADCP query script for when status is needed. Do not poll from the daemon. |
| Volume control | The VPL-XW5000ES has no volume/speaker ADCP commands. It is a projector, not a TV. Audio goes through a separate AVR. | Route audio through an AVR and use its remote for volume. |

## Feature Dependencies

```
WiFi-to-Ethernet NAT Bridge (independent, no code deps on IR bridge)
    \
     +--> Projector is reachable on 192.168.4.x

gpio-ir overlay + ir-keytable keymap loaded (kernel/boot config)
    --> IR Listener (evdev reads /dev/input/eventN, auto-detects rc device)
        --> Command Mapper (scancode lookup, debounce/repeat logic)
            --> ADCP Client (connect, SHA256 auth, send command, parse response)

Config System (YAML loader + dataclass validation)
    --> Command Mapper (reads scancode-to-ADCP mapping)
    --> ADCP Client (reads projector IP, port, password, retry settings)
    --> IR Listener (reads device path override, protocol preference)

Discover Mode
    --> IR Listener (reads raw scancodes, prints them, no ADCP sends)
    --> Populates YAML config (user copies scancodes into mapping file)

Mock ADCP Server (development/testing only)
    --> ADCP Client tests (no projector needed)
    --> Full pipeline tests (IR event -> command mapper -> ADCP send)

systemd Service
    --> ExecStartPre: loads ir-keytable keymap
    --> Restart=always: auto-recovers from crashes
    --> WatchdogSec (optional): requires sd_notify from daemon loop
```

## MVP Recommendation

The MVP is the minimum feature set that makes the remote control work again. Everything is built in dependency order, with hardware-independent work first.

**Prioritize (in build order):**

1. **ADCP client with SHA256 auth** -- The foundation. Everything depends on sending commands to the projector. Testable on any machine with a mock server or the real projector.
2. **Config system (YAML + dataclasses)** -- Defines the mapping format and projector connection settings. Needed before the command mapper.
3. **Mock ADCP server** -- Enables full pipeline testing without the projector. Unblocks all subsequent development and testing.
4. **Command mapper with debounce/repeat** -- The translation layer between IR scancodes and ADCP commands with proper timing.
5. **Main application with discover mode** -- CLI entry point, signal handling, asyncio loop. Completes the "run on dev machine against mock" story.
6. **IR listener with auto-detect** -- evdev-based listener for gpio_ir_recv. First hardware-dependent piece (needs Pi + TSOP38238).
7. **WiFi-to-Ethernet NAT bridge** -- Independent of IR work, can be done in parallel. Required for the Pi to reach the projector.
8. **systemd services + install script** -- Final deployment. Makes it boot-persistent and unattended.

**Defer (add after initial deployment when real-world usage reveals the need):**
- **Hardware watchdog**: Crashes are covered by systemd Restart=always. Hangs need observed evidence before adding watchdog complexity.
- **Config reload without restart**: Restarts take <2 seconds. Mapping changes are rare after initial setup.
- **Structured JSON logging**: Add when log parsing becomes a diagnosed problem.
- **Picture preset / aspect / motionflow mappings**: Just more YAML entries. Add as scancodes are discovered during use. Zero code change.

## Sources

- [Sony VPL-XW5000ES RM-PJ28 Remote Control Help Guide](https://helpguide.sony.net/vpl/xw5000/v1/en/contents/TP1000558977.html) -- complete button inventory for the remote
- [Sony VPL-XW5000ES ADCP Settings](https://helpguide.sony.net/vpl/xw5000/v1/en/contents/TP1000558245.html) -- port 53595, auth, 60s timeout, IP restriction
- [kennymc-c/ucr-integration-sonyADCP](https://github.com/kennymc-c/ucr-integration-sonyADCP) -- most complete open-source ADCP implementation with SHA256 auth, command sequences, error handling
- [Home Assistant Sony ADCP Control Thread](https://community.home-assistant.io/t/sony-projector-adcp-control/933745) -- real-world ADCP usage, VPL-XW5000 limitations (no volume), error patterns
- [tokyotexture/homeassistant-custom-components](https://github.com/tokyotexture/homeassistant-custom-components) -- simpler HA ADCP component reference
- [SB-Projects Sony SIRC Protocol](https://www.sbprojects.net/knowledge/ir/sirc.php) -- SIRC timing (45ms repeat frames), 12/15/20-bit variants, LSB-first encoding
- [Linux ir-keytable rc_keymap(5)](https://manpages.debian.org/testing/ir-keytable/rc_keymap.5.en.html) -- TOML keymap format, sony protocol variants (sony-12, sony-15, sony-20)
- [Raspberry Pi GPIO IR Receiver Forum](https://forums.raspberrypi.com/viewtopic.php?t=205490) -- gpio-ir overlay setup, evdev integration, kernel driver details
- [Linux kernel RC-core repeat handling](https://linux-media.vger.kernel.narkive.com/9c4yZ12r/ir-remote-control-autorepeat-evdev) -- REP_DELAY=500ms, REP_PERIOD=125ms defaults, native vs software repeat
- [Raspberry Pi systemd watchdog](https://forums.raspberrypi.com/viewtopic.php?t=376126) -- hardware watchdog 15s max, sd_notify integration, Restart=always vs WatchdogSec
- [Global Cache iTach IP2IR](https://globalcache.co.uk/products/global-cache-ip2ir-itach-tcp-ip-to-ir-infrared) -- commercial IR-to-IP bridge feature reference (8 connections, 3 IR outputs, auto-discovery)
- [chtimi59/irbridge](https://github.com/chtimi59/irbridge) -- open-source IR-to-TCP bridge daemon, WiFi reconnection handling
