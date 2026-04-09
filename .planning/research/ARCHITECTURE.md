# Architecture Patterns

**Domain:** IR-to-ADCP projector bridge daemon
**Researched:** 2026-04-09

## Recommended Architecture

```
                        +------------------+
                        |   Sony Remote    |
                        +--------+---------+
                                 | Sony SIRC IR (38kHz modulated)
                        +--------v---------+
                        |   TSOP38238      |
                        |   (GPIO 18)      |
                        +--------+---------+
                                 | Demodulated logic-level signal
                 +---------------v----------------+
                 |   Linux Kernel (gpio-ir)       |
                 |   Interrupt-driven decode      |
                 |   SIRC protocol -> scancode    |
                 |   ir-keytable keymap applied   |
                 |   -> /dev/input/eventN         |
                 +---------------+----------------+
                                 | evdev events (EV_MSC + EV_KEY)
                 +---------------v----------------+
                 |   IR Listener (ir_listener.py) |
                 |   async_read_loop()            |
                 |   Pairs MSC_SCAN + EV_KEY      |
                 +---------------+----------------+
                                 | scancode + key_state callback
                 +---------------v----------------+
                 |   Command Mapper               |
                 |   (command_mapper.py)           |
                 |   - Scancode -> ADCP lookup    |
                 |   - Debounce (one-shot cmds)   |
                 |   - Repeat (held buttons)      |
                 |   - Rate limit (100ms min)     |
                 +---------------+----------------+
                                 | ADCP command string
                 +---------------v----------------+
                 |   ADCP Client (adcp_client.py) |
                 |   - TCP connect :53595         |
                 |   - SHA256 challenge-response  |
                 |   - Send command + read reply  |
                 |   - Close connection           |
                 +---------------+----------------+
                                 | TCP
                 +---------------v----------------+
                 |   Sony VPL-XW5000ES            |
                 |   (192.168.4.2:53595)          |
                 +--------------------------------+


              NETWORK TOPOLOGY (Independent)
              ==============================

[Home WiFi Router]
      |  (DHCP, internet)
      v
[RPi wlan0]  (home network IP)
      |  (NAT / MASQUERADE)
      v
[RPi eth0]  (192.168.4.1/24, DHCP server)
      |  (ethernet cable)
      v
[Projector eth0]  (~192.168.4.2 via DHCP)
```

## Component Boundaries

| Component | File | Responsibility | Communicates With | Async? |
|-----------|------|---------------|-------------------|--------|
| Config Loader | config.py | Parse YAML, validate, return typed dataclasses | All components at startup | No |
| ADCP Client | adcp_client.py | TCP connect, SHA256 auth, send, parse response | Command Mapper (called by), Projector (TCP) | Yes |
| IR Listener | ir_listener.py | Auto-detect rc device, read evdev, emit scancodes | Command Mapper (callback) | Yes |
| Command Mapper | command_mapper.py | Scancode lookup, debounce/repeat, rate limit | IR Listener (receives), ADCP Client (calls) | Yes |
| Main Daemon | __main__.py | CLI args, asyncio loop, signal handling, wiring | All components (orchestrates) | Yes |
| Mock Server | mock_projector.py | Simulate ADCP for dev/testing | ADCP Client (in tests) | Yes |
| WiFi Bridge | setup-wifi-bridge.sh | NAT, DHCP, IP forwarding | Independent of IR bridge | No |

## Data Flow: Button Press to Projector Response

```
Time   Layer                  Event
-----  -----                  -----
T+0ms  Hardware               Remote sends 38kHz SIRC burst
T+1ms  TSOP38238              Demodulates to logic-level pulse train
T+2ms  Kernel gpio-ir         Interrupt handler captures pulse timing
T+25ms Kernel rc-core         Decodes SIRC -> scancode 0x10015
T+25ms Kernel evdev           Emits EV_MSC/MSC_SCAN + EV_KEY events
T+26ms ir_listener.py         async_read_loop yields events
T+26ms ir_listener.py         Calls callback(scancode=0x10015, state=1)
T+27ms command_mapper.py      Looks up 0x10015 -> 'power "on"'
T+27ms adcp_client.py         asyncio.open_connection(192.168.4.2, 53595)
T+30ms adcp_client.py         Reads "NOKEY\r\n" (or challenge)
T+31ms adcp_client.py         Sends 'power "on"\r\n'
T+50ms adcp_client.py         Reads "ok\r\n", closes connection
T+~2s  Projector              Lamp begins warming up
```

Total software latency: ~25ms. Perceptible latency dominated by projector response time.

## Detailed Component Design

### Config Loader (config.py)

Dataclass-based configuration with cascading file search.

```python
@dataclass
class ProjectorConfig:
    ip: str                    # Projector IP (default: 192.168.4.2)
    port: int = 53595          # ADCP port
    password: str = ""         # Empty = NOKEY auth
    timeout: float = 5.0       # TCP timeout in seconds
    retry_attempts: int = 2
    retry_delay: float = 1.0

@dataclass
class IRConfig:
    device: str = "auto"       # "auto" or explicit /dev/input/eventN
    protocol: str = "sony"
    repeat_delay_ms: int = 400
    repeat_rate_ms: int = 200

@dataclass
class CommandMapping:
    scancode: int              # Hex scancode from remote
    adcp_command: str          # e.g. 'power "on"'
    description: str           # Human-readable label
    repeatable: bool = False   # True for nav keys
```

File search order: `./config.yaml` -> `~/.config/projector-bridge/config.yaml` -> `/etc/projector-bridge/config.yaml`

### ADCP Client (adcp_client.py)

Open-per-command with asyncio streams. No persistent connection.

**Connection lifecycle:**
1. `asyncio.open_connection()` wrapped in `asyncio.wait_for(timeout=5s)`
2. Read first line. If "NOKEY" -> skip to step 4
3. Compute `sha256((challenge + password).encode()).hexdigest()`, send, read "ok"
4. Send command (`'power "on"\r\n'`), read response
5. Close: `writer.close()` + `await writer.wait_closed()`

**Critical:** The `wait_for()` timeout on `open_connection` is essential. Without it, connecting to an unreachable host blocks for 30-120 seconds (OS TCP timeout), freezing the event loop.

**Error handling:**
- `ConnectionRefusedError` / `TimeoutError` -> retry with backoff
- `err_auth` -> log, do NOT retry (wrong password)
- `err_cmd` / `err_val` -> log warning, do NOT retry (bad command)
- `err_inactive` -> projector in deep standby, log warning

### IR Listener (ir_listener.py)

**Key architectural decision: Read EV_MSC/MSC_SCAN, not EV_KEY.**

The scancode from MSC_SCAN is the stable identifier from the remote protocol. Keycodes are an unnecessary translation layer -- we map scancode -> ADCP directly. The ir-keytable keymap still needs placeholder entries so the kernel doesn't discard events, but the daemon uses the scancode.

**Event pairing pattern:**
```python
async def listen(self, callback):
    device = self._find_rc_device()
    async for event in device.async_read_loop():
        if event.type == ecodes.EV_MSC and event.code == ecodes.MSC_SCAN:
            self._last_scancode = event.value
        elif event.type == ecodes.EV_KEY:
            if self._last_scancode is not None:
                await callback(self._last_scancode, event.value)
                self._last_scancode = None
```

### Command Mapper (command_mapper.py)

Three behaviors by command type:

| Key State | repeatable=true | repeatable=false |
|-----------|-----------------|------------------|
| 1 (down) | Send immediately | Send immediately |
| 2 (repeat) | Send at rate limit | Suppress |
| 0 (up) | Ignore | Ignore |

Global rate limit: 100ms minimum between any ADCP sends.

Unknown scancodes: logged at INFO level with hex value (passive discover mode).

## Patterns to Follow

### Pattern 1: Callback Composition

Wire components via callbacks, not class hierarchies. Each component independently testable.

```python
listener = IRListener(config.ir)
mapper = CommandMapper(config.commands)
client = ADCPClient(config.projector)

async def on_ir_event(scancode: int, state: int):
    command = mapper.map(scancode, state)
    if command:
        result = await client.send(command)
        logger.info(f"{command} -> {result}")

await listener.listen(on_ir_event)
```

### Pattern 2: Graceful Degradation

If ADCP send fails, log and continue listening. Never crash on transient network errors. The projector might be off, unreachable, or slow. IR listener must keep running.

### Pattern 3: Structured Logging

Use Python `logging` with scancode hex, command, and result. systemd journal captures stdout. Debug via `journalctl -u projector-bridge`.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Persistent TCP with Reconnect

**Why bad:** Projector drops connections at 60s idle, requires per-connection auth. Persistent connections need keepalive, stale detection, reconnection, state tracking -- more complex than open-per-command with zero benefit at <1 cmd/sec.

### Anti-Pattern 2: Threading for IR + Network

**Why bad:** evdev has native asyncio support. asyncio TCP streams are stdlib. Threading adds synchronization, race conditions, harder debugging for zero benefit.

### Anti-Pattern 3: LIRC Userspace Daemon

**Why bad:** Legacy. Kernel rc-core handles protocol decoding natively since kernel 4.19. LIRC adds an unnecessary daemon and IPC hop.

### Anti-Pattern 4: Polling for Events

**Why bad:** `while True: read_one(); sleep()` wastes CPU or adds latency. `async_read_loop()` uses epoll internally, zero CPU while idle.

## Build Order (Dependency-Driven)

```
Phase 1: Config Loader (everything depends on it)
    v
Phase 2: ADCP Client + Mock Server (testable without hardware)
    v
Phase 3: Command Mapper (needs config + client)
    v
Phase 4: Main Daemon + Tests (wires everything, mock-testable)
    v
Phase 5: IR Listener + Keymap (first hardware dependency)
    v
Phase 6: WiFi Bridge (independent, needs Pi)
    v
Phase 7: systemd + Deployment (needs everything working)
```

**Ordering rationale:** Front-load work testable on dev machine. Push hardware dependencies late. WiFi bridge is independent and can be done anytime after Pi access.

## Resource Profile

| Concern | Value | Notes |
|---------|-------|-------|
| Memory | ~15-30MB RSS | Python 3.11 + evdev + pyyaml. Pi 3B has 1GB |
| CPU at idle | ~0% | epoll-based event wait |
| CPU at peak | <1% | Max ~10 events/second during menu navigation |
| Startup time | <2 seconds | venv + imports + config + device open |
| SD card wear | Minimal | systemd journal rotation, WARNING level in production |

## Sources

- [Sony ADCP Protocol Manual](https://pro.sony/s3/2018/07/03140912/Sony_Protocol-Manual_1st-Edition-Revised-2.pdf) -- connection, auth, command format
- [kennymc-c/ucr-integration-sonyADCP](https://github.com/kennymc-c/ucr-integration-sonyADCP) -- SHA256 auth reference
- [python-evdev tutorial](https://python-evdev.readthedocs.io/en/latest/tutorial.html) -- async_read_loop API
- [Linux rc-core docs](https://docs.kernel.org/driver-api/media/rc-core.html) -- kernel IR architecture
- [RPi gpio-ir forum thread](https://forums.raspberrypi.com/viewtopic.php?t=205490) -- device detection, real-world usage
