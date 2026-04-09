# Domain Pitfalls

**Domain:** IR-to-ADCP Projector Bridge on Raspberry Pi
**Researched:** 2026-04-09

## Critical Pitfalls

Mistakes that cause rewrites, bricked systems, or complete feature failure.

### Pitfall 1: Sony SIRC Scancode Format Confusion

**What goes wrong:** Sony SIRC scancodes exist in at least three incompatible representations across different tools, libraries, and documentation sources. The kernel's ir-keytable/evdev reports scancodes with device address in bits 16+, function in bits 0-6. Arduino libraries, ESPHome, and LIRC use completely different bit orderings (some with bit reversal within each field). Community databases (remotecentral.com, hifi-remote.com) publish codes in yet another format. Developers often copy codes from one source into a keymap expecting the kernel format, and nothing works.

**Why it happens:** Sony's SIRC protocol transmits bits LSB-first (command then address), but the kernel re-assembles them into a 32-bit integer with device in upper bits and function in lower bits. Documentation sites often show the raw transmission order. The 12/15/20-bit variants further complicate things because the same button produces different scancodes depending on which protocol variant the decoder matched.

**Consequences:** The entire keymap is wrong. Buttons map to incorrect ADCP commands or are not recognized at all. Since the projector remote's exact codes are undocumented, there is no authoritative reference to cross-check against.

**Prevention:**
- Use discover mode exclusively as the source of truth -- capture scancodes directly from `ir-keytable -t -s rc0` output while pressing each button on the actual remote. Never copy scancodes from internet databases.
- Force a specific protocol variant in the gpio-ir overlay config (`rc-map-name`) and ir-keytable (`-p sony`) so the kernel decoder is deterministic.
- Log the raw hex scancode alongside every event in discover mode so mappings are traceable.

**Detection:** Buttons produce no response or wrong response. Discover mode shows different scancodes than what is in the keymap file.

**Phase:** Must be addressed in the IR listener phase. Discover mode is not optional -- it is the primary tool for building the scancode mapping.

---

### Pitfall 2: ADCP Authentication Flow Misimplementation

**What goes wrong:** The ADCP SHA256 challenge-response has a specific flow: connect to TCP:53595, receive a challenge string (or "NOKEY" if auth is disabled), concatenate challenge+password, SHA256 hash it, send the hex digest back. Developers get the concatenation order wrong (password+challenge instead of challenge+password), forget to convert the hash to lowercase hex ASCII, or fail to handle both NOKEY and challenge paths. The projector responds with "err_auth" and drops the connection.

**Why it happens:** The Sony protocol manual PDF is behind a 403/paywall on some hosting. The authentication flow is only documented briefly. Reference implementations (kennymc-c/ucr-integration-sonyADCP, tokyotexture SONY_ADCP.py) implement it differently and are in different languages. Developers fill in gaps with assumptions.

**Consequences:** Cannot send any commands to the projector. Every connection attempt fails at the auth stage. Since the error message is just "err_auth", it is unclear whether the problem is the password, the hash computation, or the concatenation order.

**Prevention:**
- Study the kennymc-c implementation (the most complete reference with SHA256 auth) before writing any auth code.
- Implement NOKEY detection first (disable auth on the projector during development). Get commands working, then layer in auth.
- Use Wireshark on the Pi to capture the actual challenge string and verify the hash computation independently.
- Add debug logging that prints the challenge received, the concatenated string (masked for password), and the hash sent.
- Write unit tests for the hash computation with known test vectors.

**Detection:** "err_auth" response from projector on every connection. Wireshark shows the hash being sent but projector rejecting it.

**Phase:** Must be addressed in the ADCP client phase. Test with auth disabled first, add auth as a separate step.

---

### Pitfall 3: Projector Unreachable in Deep Standby

**What goes wrong:** When the Sony VPL-XW5000ES is in standby, it may not respond to TCP connections at all unless "Network Standby" (or equivalent setting like "Standby Mode: Standard") is enabled in the projector's settings menu. The ADCP service shuts down completely in deep standby. The Pi sends a `power "on"` command but the TCP connection is refused because the projector's network stack is off.

**Why it happens:** Sony projectors have multiple standby levels. The factory default is often deep standby (lowest power consumption), which powers down the network interface entirely. The user must manually change this setting via the projector's OSD menu using the physical buttons on the projector body (since the IR receiver is broken, they cannot use the remote -- but they may be able to use the projector's panel buttons).

**Consequences:** The most critical command (power on) does not work. The projector can only be powered on by physically pressing the power button on the projector body, which defeats the entire purpose of this project.

**Prevention:**
- Document the "Network Standby" / "Standby Mode: Standard" requirement prominently in setup instructions. This is a prerequisite, not a nice-to-have.
- During initial setup, verify the projector is reachable when in standby by attempting a TCP connection to port 53595. If it fails, guide the user to change the setting.
- Handle the connection-refused case gracefully in the daemon -- log a specific error message referencing the network standby setting rather than a generic connection error.
- Note: Enabling network standby increases the projector's standby power consumption (~0.5W to ~6W). This is an acceptable tradeoff.

**Detection:** Power-on command fails. TCP connection to 53595 is refused (not just timed out) when projector is in standby.

**Phase:** Must be addressed in both the ADCP client phase (error handling) and documentation/setup phase. Should be the first thing tested during hardware integration.

---

### Pitfall 4: IR Repeat/Hold Flooding the Projector

**What goes wrong:** When a user holds a button (e.g., volume up on an AV receiver remote, or menu navigation), the IR sensor generates key-down, repeat, repeat, repeat... events at ~125ms intervals (default REP_PERIOD). Each repeat event triggers an ADCP command. But the open-per-command model means each command requires connect + auth + send + close, taking 30-100ms+ per round trip. The commands queue up faster than they can be sent, creating a growing backlog. The projector receives a flood of commands and may respond erratically or slowly.

**Why it happens:** evdev's repeat mechanism is designed for keyboards, not for controlling a projector over a network. The repeat rate (8 events/second) is fine for keyboard repeat but overwhelming for a TCP-per-command model. Additionally, some ADCP commands (like menu navigation) have a response time of 30-1000ms per the Sony protocol spec.

**Consequences:** Menu navigation is sluggish and unpredictable. The projector processes queued commands after the user releases the button, causing continued movement. Power toggle could be sent multiple times, turning the projector off then on again.

**Prevention:**
- Implement per-command-type debounce/throttle in the IR-to-ADCP mapping layer. Different command types need different strategies:
  - **Toggle commands** (power): Only send on key-down (value=1), ignore repeat (value=2) and key-up (value=0). Add a cooldown of several seconds.
  - **Navigational commands** (menu up/down/left/right): Send on key-down, then rate-limit repeats to one every 300-500ms.
  - **Continuous commands** (volume -- if applicable): Rate-limit to projector's processing speed.
- Use the evdev event value field: 0=key up, 1=key down, 2=repeat hold. Filter at this level.
- If a command is already in-flight for a given key, drop new repeats rather than queuing them.
- Consider tuning the kernel repeat parameters via `ir-keytable --delay 500 --period 250` to reduce repeat frequency at the source.

**Detection:** User holds a navigation button and the projector continues responding after release. Power toggles unexpectedly. Log shows command queue growing.

**Phase:** Must be addressed in the IR-to-ADCP bridge logic phase. This is core business logic, not an afterthought.

---

### Pitfall 5: WiFi Drops Kill the NAT Bridge (and SSH Access)

**What goes wrong:** The Raspberry Pi 3B's built-in WiFi (BCM43438) drops the wlan0 connection under various conditions: weak signal, power saving kicks in, DHCP lease renewal fails, or the WiFi chip firmware has a known bug. When wlan0 drops, the NAT bridge dies -- the projector loses internet access and, critically, the operator loses SSH access to the Pi (since the only network path to the Pi is through WiFi).

**Why it happens:** The Pi 3B's WiFi chip has known firmware issues (Cypress firmware was rolled back after introducing problems). The default WiFi power management aggressively suspends the radio. Link quality below 50 causes significant degradation. The Pi is typically ceiling-mounted near a projector, far from the router, with the metal projector body potentially blocking the signal.

**Consequences:** Projector loses network access intermittently. The operator cannot SSH into the Pi to diagnose or fix the problem (chicken-and-egg). If the Pi has no other access method (serial console, keyboard/monitor), the only recovery is physical access -- which may require a ladder if ceiling-mounted.

**Prevention:**
- Disable WiFi power management: add `wireless-power off` to the wlan0 config or create `/etc/NetworkManager/conf.d/default-wifi-powersave-on.conf` with `wifi.powersave = 2`.
- Set `connection.autoconnect-retries=0` (unlimited retries) in NetworkManager, or use a systemd timer that checks wlan0 status and restarts the interface if down.
- Deploy a simple watchdog script/timer that pings the gateway and bounces wlan0 if unreachable for N seconds.
- Position the Pi for best WiFi signal possible (antenna orientation matters on the Pi 3B -- the antenna is in the top-right corner of the board).
- Consider a USB WiFi dongle with external antenna if the built-in chip is unreliable in the installation location.
- Ensure the IR bridge daemon itself does NOT depend on WiFi being up -- it communicates with the projector over eth0, which is a direct connection.

**Detection:** SSH connection drops intermittently. Projector loses internet access. `journalctl -u NetworkManager` shows frequent reconnection attempts.

**Phase:** Must be addressed in the WiFi bridge phase with a connectivity watchdog. Should be tested during physical installation.

---

### Pitfall 6: SD Card Corruption from Power Loss

**What goes wrong:** The Raspberry Pi is typically powered from a source that may be switched off (e.g., a power strip, a circuit controlled by a home automation system, or simply unplugging). Any write to the SD card at the moment of power loss can corrupt the filesystem, rendering the Pi unbootable. This is especially likely because the Pi runs a daemon that writes logs, and the OS itself has periodic writes (journald, tmpfiles, etc.).

**Why it happens:** SD cards have no power-loss protection. ext4's journaling mitigates but does not eliminate corruption. The Pi has no shutdown button, and users treat it like an appliance that can be unplugged.

**Consequences:** Pi does not boot. Requires physical access to reflash the SD card, which means removing it from a ceiling-mounted installation.

**Prevention:**
- Set up a read-only root filesystem (`overlayfs` or `raspi-config` overlay mode). This is the single most important reliability measure for an embedded Pi.
- Redirect all logs to tmpfs (`/tmp` or `/run`), or use `journald`'s `Storage=volatile` setting.
- Store the YAML config on the read-only partition (it changes rarely). If config changes are needed, temporarily remount rw.
- Use `fsck` on boot (add `fsck.repair=yes` to `/boot/firmware/cmdline.txt`).
- If read-only root is too complex, at minimum use `sync` mount options and minimize writes.

**Detection:** Pi fails to boot after a power event. `fsck` reports errors. Logs show filesystem remounted read-only after errors.

**Phase:** Should be addressed in the deployment/hardening phase. Not needed during development, but critical for production reliability.

## Moderate Pitfalls

### Pitfall 7: gpio-ir Overlay Not Loading or Wrong Protocol Active

**What goes wrong:** The `dtoverlay=gpio-ir,gpio_pin=18` line in `/boot/firmware/config.txt` does not take effect, or the kernel's IR decoder defaults to `rc-rc6-mce` protocol and ignores Sony SIRC packets. The ir-keytable daemon may not run at boot, or the custom keymap file is not loaded.

**Prevention:**
- Verify the overlay is loaded after boot with `dtoverlay -l` or check `dmesg | grep gpio_ir_recv`.
- Explicitly set the protocol and keymap with `ir-keytable -p sony -c -w /path/to/keymap.toml` and persist via a systemd unit that runs after the rc device appears.
- The keymap file must be in TOML format (not the old plain-text format) for modern ir-keytable versions. Filename and path matter -- `/etc/rc_keymaps/` is the standard location but the udev rule that auto-loads may not work reliably; use an explicit systemd service instead.
- Test with `ir-keytable -t -s rc0` to verify events are being received before writing any Python code.

**Phase:** IR listener phase. This is the very first thing to validate on the hardware.

---

### Pitfall 8: ADCP Connection Timeout Races

**What goes wrong:** The projector's ADCP server has a 60-second idle timeout. The open-per-command model avoids this, but introduces a different race: if the user presses buttons rapidly, multiple concurrent connection attempts may occur. The projector may only accept one TCP connection at a time (this is common for projector control protocols). The second connection attempt gets refused or queued, causing command loss.

**Prevention:**
- Serialize all ADCP commands through a single asyncio queue. Never open concurrent connections.
- Use an async lock to ensure only one connect-auth-send-close cycle happens at a time.
- If a command is waiting in the queue while another is in flight, consider whether to drop it (for repeats) or queue it (for distinct commands).
- Set a reasonable timeout on the TCP connect (2-3 seconds) and auth phase (2 seconds) so a hung connection does not block the queue forever.

**Phase:** ADCP client phase. The serialization/queuing architecture must be designed upfront, not bolted on.

---

### Pitfall 9: evdev Device Path Changes Across Reboots

**What goes wrong:** The IR receiver's evdev device path (`/dev/input/eventN`) may change between reboots as the kernel assigns numbers based on device enumeration order. Code that hardcodes `/dev/input/event0` breaks when another input device loads first.

**Prevention:**
- Never hardcode the event device path. Use `python-evdev`'s `InputDevice.list_devices()` and filter by device name (e.g., `"gpio_ir_recv"`) or by the input device's capabilities.
- Alternatively, use the stable symlink under `/dev/input/by-path/` or a udev rule that creates a predictable symlink like `/dev/input/ir-receiver`.
- Handle the case where the device is not found at startup (IR overlay not loaded) with a clear error message.

**Phase:** IR listener phase. Use device discovery from the start, never hardcode.

---

### Pitfall 10: dnsmasq/DHCP Race Condition at Boot

**What goes wrong:** On the WiFi bridge, dnsmasq starts before dhcpcd/NetworkManager finishes configuring eth0's static IP. dnsmasq fails to bind to the interface, DHCP does not serve addresses on the eth0 subnet, and the projector does not get an IP address.

**Prevention:**
- Configure the systemd service ordering: dnsmasq must `After=network-online.target` and the eth0 static configuration must be complete before dnsmasq starts.
- Use `bind-dynamic` instead of `bind-interfaces` in dnsmasq.conf so it retries binding if the interface is not ready yet.
- Test by rebooting the Pi and verifying the projector gets a DHCP lease within 30 seconds of boot.

**Phase:** WiFi bridge phase. Must be verified by full reboot testing, not just service restarts.

---

### Pitfall 11: iptables NAT Rules Not Persisting Across Reboots

**What goes wrong:** The NAT masquerade rule (`iptables -t nat -A POSTROUTING -o wlan0 -j MASQUERADE`) and the FORWARD rule work after manual setup, but are lost after reboot because iptables rules are not persistent by default.

**Prevention:**
- Install `iptables-persistent` and save rules with `netfilter-persistent save` after configuration.
- Alternatively, use a systemd oneshot service that applies the rules at boot.
- Also ensure `net.ipv4.ip_forward=1` is set in `/etc/sysctl.d/` (not just runtime via `sysctl -w`).
- Verify by rebooting and confirming `iptables -t nat -L` and `sysctl net.ipv4.ip_forward` show the correct values.

**Phase:** WiFi bridge phase. Include in the setup/deployment automation.

## Minor Pitfalls

### Pitfall 12: ADCP Commands During Power State Transitions

**What goes wrong:** Sending commands while the projector is warming up (after power on, takes 30-60 seconds) or cooling down (after power off, takes 60-90 seconds) may return errors or be silently ignored. The Sony protocol manual indicates response times vary from 30ms to 1000ms depending on command and projector state.

**Prevention:**
- After sending `power "on"`, poll `power_status ?` until it reports "standby" -> "startup" -> "power_on" before sending other commands. Or simply log a warning and let the user retry.
- Do not attempt input switching or menu navigation during warm-up/cool-down.
- Consider a simple state machine: UNKNOWN -> STANDBY -> WARMING -> ON -> COOLING -> STANDBY.

**Phase:** ADCP client phase, but can be deferred to a polish/reliability iteration.

---

### Pitfall 13: Python evdev Requires Root or Input Group

**What goes wrong:** The daemon crashes with "Permission denied" when opening the evdev input device because the systemd service runs as a non-root user who is not in the `input` group.

**Prevention:**
- Either run the service as root (acceptable for a single-purpose embedded device) or add the service user to the `input` group.
- If using a udev rule for the IR device, set `MODE="0660"` and `GROUP="input"`.
- Test the systemd service with `sudo systemctl start ...`, do not just test with `sudo python3 ...`.

**Phase:** Deployment phase. Easy to fix but easy to miss during development when testing as root.

---

### Pitfall 14: Multiple evdev Nodes for a Single IR Receiver

**What goes wrong:** Some IR receiver configurations create two `/dev/input/eventN` nodes. Only one provides actual keystrokes. The daemon opens the wrong one and receives no events.

**Prevention:**
- In discover mode, list all input devices and show their capabilities. The correct device will have `EV_KEY` and `EV_MSC` capabilities.
- Use python-evdev's capability introspection to validate the chosen device.

**Phase:** IR listener phase. Handle in device discovery logic.

---

### Pitfall 15: ADCP IP Filtering Locks Out the Pi

**What goes wrong:** The projector's ADCP settings include an IP whitelist. If the Pi's IP changes (DHCP reassignment on wlan0, or the eth0 static IP is misconfigured), the projector rejects all ADCP connections from the new IP. Since the projector's IR receiver is broken, changing the ADCP settings requires the projector's web UI, which itself may be unreachable if network settings are wrong.

**Prevention:**
- Do not configure the ADCP IP whitelist on the projector, or if you must, use the Pi's static eth0 IP (which does not change).
- Document the recovery path: projector panel buttons can access settings menus. Factory reset is the nuclear option.
- Use a static IP for eth0 (the direct Pi-to-projector link) and ensure it never changes.

**Phase:** Setup/documentation phase. A configuration landmine that should be called out in setup instructions.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| IR Listener | gpio-ir overlay not loading, wrong protocol (Pitfall 7) | Validate hardware first with ir-keytable -t before writing code |
| IR Listener | Scancode format confusion (Pitfall 1) | Only use discover mode output, never copy codes from internet |
| IR Listener | Device path changes (Pitfall 9) | Discover device by name, never hardcode path |
| ADCP Client | Auth misimplementation (Pitfall 2) | Develop with auth disabled first, add later |
| ADCP Client | Connection serialization (Pitfall 8) | Design async queue from day one |
| ADCP Client | Projector unreachable in standby (Pitfall 3) | Document and verify Network Standby setting early |
| IR-to-ADCP Bridge | Button repeat flooding (Pitfall 4) | Debounce/throttle is core logic, not an optimization |
| WiFi Bridge | dnsmasq boot race (Pitfall 10) | Use bind-dynamic, test with full reboots |
| WiFi Bridge | iptables not persisting (Pitfall 11) | iptables-persistent or systemd oneshot |
| WiFi Bridge | WiFi drops (Pitfall 5) | Disable power management, deploy watchdog |
| Deployment | SD card corruption (Pitfall 6) | Read-only rootfs or overlay mode |
| Deployment | Permissions (Pitfall 13) | Test as systemd service, not as root in terminal |

## Sources

- [Raspberry Pi Forums: GPIO IR remote](https://forums.raspberrypi.com/viewtopic.php?t=205490)
- [Raspberry Pi Forums: IR Remote / ir-keytable / TSOP38238](https://forums.raspberrypi.com/viewtopic.php?t=284321)
- [Linux Kernel: RC Protocols and Scancodes](https://docs.kernel.org/userspace-api/media/rc/rc-protos.html)
- [Debian: ir-keytable rc_keymap man page](https://manpages.debian.org/testing/ir-keytable/rc_keymap.5.en.html)
- [Sony VPL-XW5000 ADCP Help Guide](https://helpguide.sony.net/vpl/xw5000/v1/en/contents/TP1000558245.html)
- [Sony ADCP Protocol Manual (Common)](https://pro.sony/s3/2018/07/03140912/Sony_Protocol-Manual_1st-Edition-Revised-2.pdf)
- [kennymc-c/ucr-integration-sonyADCP](https://github.com/kennymc-c/ucr-integration-sonyADCP)
- [Home Assistant: Sony ADCP Projector Control](https://community.home-assistant.io/t/sony-projector-adcp-control/933745)
- [Home Assistant: Confusion around Sony IR codes (SIRC)](https://community.home-assistant.io/t/confusion-around-sony-infrared-codes-sirc/699878)
- [SB-Projects: Sony SIRC Protocol](https://www.sbprojects.net/knowledge/ir/sirc.php)
- [hifi-remote.com: Sony IR remote control codes](https://www.hifi-remote.com/sony/)
- [Python-evdev Tutorial](https://python-evdev.readthedocs.io/en/latest/tutorial.html)
- [Python-evdev API Reference](https://python-evdev.readthedocs.io/en/latest/apidoc.html)
- [Hackaday: Raspberry Pi SD Card Corruption](https://hackaday.com/2022/03/09/raspberry-pi-and-the-story-of-sd-card-corruption/)
- [Raspberry Pi Forums: SD Card power failure resilience](https://forums.raspberrypi.com/viewtopic.php?t=253104)
- [Raspberry Pi Forums: WiFi connection unstable](https://forums.raspberrypi.com/viewtopic.php?t=188891)
- [Raspberry Pi Forums: Pi 3B WiFi disconnecting](https://forums.raspberrypi.com/viewtopic.php?t=373043)
- [Will Haley: Raspberry Pi WiFi Ethernet Bridge](https://www.willhaley.com/blog/raspberry-pi-wifi-ethernet-bridge/)
- [LibreELEC: IR Remotes Configuration](https://wiki.libreelec.tv/configuration/ir-remotes)
- [Pi My Life Up: Raspberry Pi Watchdog](https://pimylifeup.com/raspberry-pi-watchdog/)
