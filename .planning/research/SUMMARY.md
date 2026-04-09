# Research Summary: Sony Projector IR-to-ADCP Bridge

**Domain:** Embedded IR-to-network protocol bridge daemon (Raspberry Pi)
**Researched:** 2026-04-09
**Overall confidence:** HIGH

## Executive Summary

This project has a well-defined, narrow scope: receive Sony SIRC IR commands via a TSOP38238 sensor on a Raspberry Pi 3B and translate them into ADCP (Advanced Display Control Protocol) commands sent over TCP to a Sony VPL-XW5000ES projector with a broken IR receiver. A secondary function provides WiFi-to-Ethernet NAT bridging so the projector (ethernet-only) can reach the network through the Pi's WiFi.

The technology stack is mature and well-understood. The kernel's gpio-ir overlay handles IR decoding in interrupt-driven kernel space, eliminating the reliability problems of userspace approaches (pigpio, LIRC). Python evdev provides native asyncio integration for reading input events. The ADCP protocol is a simple ASCII-over-TCP protocol with SHA256 challenge-response auth, implementable with Python's asyncio stdlib alone. The only runtime dependencies are evdev and PyYAML -- two stable, well-maintained libraries.

The architecture is a straightforward event-driven pipeline: kernel IR decode -> evdev event -> scancode lookup + debounce -> ADCP TCP command -> projector response. Single-threaded asyncio handles both the IR event loop and TCP I/O without threading. The open-per-command TCP model (connect, auth, send, close) avoids persistent connection complexity given the projector's 60-second idle timeout.

The primary risks are not in the software but at the hardware/protocol boundary: undocumented Sony remote scancodes (mitigated by discover mode), projector deep standby rejecting ADCP (mitigated by documenting the Network Standby prerequisite), and the SHA256 auth hash encoding being sensitive to exact byte-level details (mitigated by referencing the kennymc-c implementation and testing against real hardware).

## Key Findings

**Stack:** Python 3.11 (Bookworm system), asyncio + evdev + PyYAML. Kernel gpio-ir for IR decoding. Two runtime dependencies, everything else is stdlib.

**Architecture:** Single-process asyncio daemon with callback-composed pipeline. Open-per-command TCP for ADCP. No threads, no web server, no message queue.

**Critical pitfall:** SHA256 auth encoding mismatch and projector deep standby are the two highest-risk failure modes. Both cause complete inability to control the projector with non-obvious root causes.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **ADCP Client + Config System** - Build and test the network/protocol layer first
   - Addresses: TCP connection, SHA256 auth, config loading, ADCP command format
   - Avoids: Auth encoding pitfall by testing early with mock server AND real projector
   - No hardware needed -- fully testable on dev machine

2. **Mock Server + Command Mapper** - Complete the non-hardware pipeline
   - Addresses: Mock ADCP for testing, debounce/repeat logic, rate limiting
   - Avoids: Button flood pitfall by designing debounce as core logic from the start
   - No hardware needed

3. **Main Daemon + Tests** - Wire everything together, comprehensive test suite
   - Addresses: CLI (--discover, --config, --log-level), signal handling, graceful shutdown
   - Avoids: Missing timeout pitfall by testing unreachable-host scenarios
   - No hardware needed

4. **IR Listener + Keymap** - First hardware dependency (Pi + sensor + remote)
   - Addresses: gpio-ir overlay, ir-keytable keymap, evdev auto-detect, discover mode
   - Avoids: Scancode format pitfall by using discover mode as sole source of truth
   - Needs Pi + TSOP38238 + Sony remote

5. **WiFi Bridge** - Independent of IR bridge, needs Pi
   - Addresses: NAT routing, DHCP, NetworkManager config
   - Avoids: NetworkManager conflict pitfall by using nmcli exclusively
   - Needs Pi with WiFi + ethernet to projector

6. **systemd + Deployment** - Final integration and hardening
   - Addresses: Auto-start, permissions, install script, documentation
   - Avoids: SD card corruption by considering read-only rootfs
   - Needs everything above working

**Phase ordering rationale:**
- ADCP client first because it can be fully tested without hardware and catches the highest-risk pitfall (auth encoding) early
- Mock server early because it enables TDD for the entire pipeline
- IR listener late because it requires physical hardware; by this point, everything downstream is tested
- WiFi bridge is independent and can be done anytime after Pi access, but logically comes after the IR bridge since it is secondary priority
- Deployment last because it is the integration of all working components

**Research flags for phases:**
- Phase 1 (ADCP Client): Needs testing against real projector to validate SHA256 auth -- mock alone is insufficient
- Phase 4 (IR Listener): Needs discover-mode session with the actual remote to build scancode map -- no documentation exists for RM-PJ28 scancodes
- Phase 5 (WiFi Bridge): NetworkManager's ipv4.method shared may use 10.42.0.0/24 by default; may need override for 192.168.4.0/24 subnet
- Phases 1-3: Standard patterns, unlikely to need additional research

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All libraries verified on PyPI with current versions. evdev 1.9.3, PyYAML 6.0.3, pytest 8.4.x/9.0.x. All compatible with Python 3.11 on Bookworm |
| Features | HIGH | Feature set is minimal and well-scoped. ADCP command set verified against Sony protocol manual and reference implementations |
| Architecture | HIGH | Single-process asyncio pipeline is the standard pattern for this type of event-driven daemon. evdev async API verified in official docs |
| Pitfalls | HIGH | Critical pitfalls (auth encoding, deep standby, scancode format) well-documented in community forums and reference implementations. Mitigations are concrete and actionable |
| WiFi Bridge | MEDIUM | NetworkManager shared mode is documented but the exact subnet customization (10.42.0.0 vs 192.168.4.0) needs testing. May fall back to manual dnsmasq |

## Gaps to Address

- **RM-PJ28 remote scancodes:** Completely undocumented. Must be discovered empirically with the actual remote during Phase 4. No amount of research can resolve this -- discover mode is the answer.
- **ADCP command completeness:** The Sony protocol manual lists commands generically. The VPL-XW5000ES may not support all of them. Testing against the real projector during Phase 1 will reveal which commands work.
- **SHA256 hash concatenation order:** Reference implementations (kennymc-c, tokyotexture) are the best source. Verify with Wireshark capture during Phase 1 hardware testing.
- **NetworkManager shared mode subnet override:** Whether nmcli con modify ipv4.addresses 192.168.4.1/24 works alongside ipv4.method shared needs testing on actual Bookworm install during Phase 5.

## Sources

All sources are documented with confidence levels in the individual research files:
- STACK.md -- Technology choices with version verification from PyPI
- FEATURES.md -- Feature landscape derived from ADCP protocol manual and project requirements
- ARCHITECTURE.md -- Component design based on evdev and asyncio official documentation
- PITFALLS.md -- Failure modes from community forums, reference implementations, and protocol documentation
