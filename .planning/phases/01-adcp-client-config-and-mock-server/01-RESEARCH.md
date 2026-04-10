# Phase 1 Research: ADCP Client, Config, and Mock Server

**Researched:** 2026-04-10
**Phase Goal:** Developer can send ADCP commands to a mock projector from the command line, with all settings driven by a YAML config file
**Requirements:** MAP-01, ADCP-01, ADCP-02, ADCP-03, ADCP-04, DEV-02

## 1. ADCP Protocol Details

### Connection Handshake Sequence

The ADCP (Advanced Display Control Protocol) operates over TCP port 53595. The exact handshake:

1. **Client connects** to `projector_host:53595` (TCP)
2. **Server sends challenge** — a plain ASCII string terminated by `\r\n`. Two cases:
   - Normal auth: Server sends a random challenge string (e.g., `a1b2c3d4e5f6`)
   - NOKEY mode: Server sends the literal string `NOKEY\r\n` when auth is disabled on the projector
3. **Client authenticates** (skip if NOKEY):
   - Compute: `hashlib.sha256((challenge + password).encode()).hexdigest()`
   - Note: concatenation order is `challenge + password`, NOT `password + challenge` (Pitfall 2)
   - Send the hex digest string back, terminated by `\r\n`
   - Server responds with `ok\r\n` on success or `err_auth\r\n` on failure
4. **Client sends command** — ASCII string terminated by `\r\n` (e.g., `power "on"\r\n`)
5. **Server responds** — one of:
   - `ok\r\n` — command accepted
   - `"value"\r\n` — query response (e.g., `power_status ?` returns `"standby"`)
   - `err_cmd\r\n` — unknown command
   - `err_val\r\n` — invalid parameter value
   - `err_auth\r\n` — authentication failure
   - `err_inactive\r\n` — projector in deep standby, network stack up but ADCP service not running
6. **Client closes connection** — open-per-command model, no keepalive

### Key Protocol Facts

- **Line termination:** `\r\n` for all messages in both directions
- **Encoding:** ASCII
- **Default password:** `"Projector"` (case-sensitive) on VPL-XW5000ES
- **Auth hash:** SHA256 of `challenge_string + password_string`, output as lowercase hex
- **Port:** 53595 (fixed, not configurable on projector side)
- **Idle timeout:** 60 seconds (projector drops idle connections)
- **Concurrent connections:** Likely single-connection only — serialization required

### Command Format

Commands follow the pattern: `command_name "parameter"\r\n`

Examples relevant to Phase 1 testing:
- `power "on"` / `power "off"` — power control
- `power_status ?` — query returns `"on"`, `"standby"`, `"startup"`, `"cooling"`
- `input "hdmi1"` / `input "hdmi2"` — input switching
- `key "menu"` / `key "up"` / `key "down"` — keypress simulation

### Error Response Mapping

| ADCP Response | Python Exception | Retryable? | Notes |
|---------------|-----------------|------------|-------|
| `err_auth` | `AuthError` | No | Wrong password or hash computation |
| `err_cmd` | `CommandError` | No | Unknown command name |
| `err_val` | `ValueError` | No | Invalid parameter for known command |
| `err_inactive` | `InactiveError` | No (but could retry with delay) | Projector in deep standby |
| Connection refused/timeout | `ConnectionError` | Yes | Network/projector issue |

## 2. Config Schema Design

### YAML Structure (from D-01 through D-04)

```yaml
projector:
  host: "192.168.4.100"      # REQUIRED
  port: 53595                 # default
  password: "Projector"       # REQUIRED
  timeout_connect: 5          # seconds, default
  timeout_read: 3             # seconds, default
  retries: 3                  # total attempts, default
  retry_delay: 0.2            # seconds (200ms base), default

mappings:
  "0x010015":                 # scancode as hex string key
    command: 'power "on"'     # ADCP command string
    repeat: false             # whether to honor key-repeat events
    description: "Power On"   # human-readable label

ir:
  device_name: "gpio_ir_recv" # auto-detect filter, default
  protocol: "sony"            # ir-keytable protocol, default
```

### Dataclass Design

```python
@dataclass
class ProjectorConfig:
    host: str                           # required, no default
    port: int = 53595
    password: str = ""                  # required at runtime, but empty string for NOKEY mode
    timeout_connect: float = 5.0
    timeout_read: float = 3.0
    retries: int = 3
    retry_delay: float = 0.2

@dataclass
class CommandMapping:
    command: str                        # ADCP command string
    repeat: bool = False
    description: str = ""

@dataclass
class IRConfig:
    device_name: str = "gpio_ir_recv"
    protocol: str = "sony"

@dataclass
class Config:
    projector: ProjectorConfig
    mappings: dict[str, CommandMapping]  # scancode hex -> mapping
    ir: IRConfig
```

### Validation Strategy

- Load with `yaml.safe_load()` — returns dict or None
- Validate required fields: `projector.host` must be present and non-empty
- Validate types: port is int, timeouts are numeric, retries is positive int
- Validate mappings: each entry must have `command` field
- Raise clear errors: `"Missing required field: projector.host"` — not generic YAML errors
- Return constructed dataclass hierarchy on success

## 3. Async TCP Client Pattern

### asyncio.open_connection Pattern

```python
async def send_command(config: ProjectorConfig, command: str) -> str:
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(config.host, config.port),
        timeout=config.timeout_connect
    )
    try:
        # Read challenge
        challenge_line = await asyncio.wait_for(
            reader.readline(),
            timeout=config.timeout_read
        )
        challenge = challenge_line.decode().strip()

        if challenge != "NOKEY":
            # Authenticate
            hash_input = challenge + config.password
            auth_hash = hashlib.sha256(hash_input.encode()).hexdigest()
            writer.write(f"{auth_hash}\r\n".encode())
            await writer.drain()

            auth_response = await asyncio.wait_for(
                reader.readline(),
                timeout=config.timeout_read
            )
            if auth_response.decode().strip() != "ok":
                raise AuthError("Authentication failed")

        # Send command
        writer.write(f"{command}\r\n".encode())
        await writer.drain()

        # Read response
        response_line = await asyncio.wait_for(
            reader.readline(),
            timeout=config.timeout_read
        )
        return parse_response(response_line.decode().strip())
    finally:
        writer.close()
        await writer.wait_closed()
```

### Retry Pattern

```python
async def send_command_with_retry(config, command):
    delay = config.retry_delay
    for attempt in range(config.retries):
        try:
            return await send_command(config, command)
        except ConnectionError:
            if attempt == config.retries - 1:
                raise
            logger.warning("Connection failed, retry %d/%d in %.1fs",
                          attempt + 1, config.retries, delay)
            await asyncio.sleep(delay)
            delay *= 2  # exponential backoff: 200ms, 400ms
```

Key design points:
- Only retry on `ConnectionError` (transient). Never retry `AuthError`, `CommandError`, `ValueError`
- `asyncio.wait_for()` wraps every I/O operation with timeout
- `writer.close()` + `await writer.wait_closed()` in `finally` block for clean resource release
- `writer.drain()` after every write to respect flow control

## 4. Mock Server Architecture

### Design: asyncio TCP Server

The mock server should simulate the real projector's ADCP protocol for development and testing. It needs to:

1. **Listen on configurable port** (default 53595, but allow override for tests)
2. **Support both auth modes:**
   - Normal: generate a random challenge string, validate SHA256 response
   - NOKEY: send "NOKEY", skip auth
3. **Accept commands and return responses:**
   - Known commands: return `ok` or query values
   - Unknown commands: return `err_cmd`
   - Invalid parameters: return `err_val`
4. **Track state** (at minimum, power state for testing queries)
5. **Be usable both standalone and as pytest fixture**

### Implementation Approach

```python
class MockProjector:
    def __init__(self, host="127.0.0.1", port=53595, password="Projector", nokey=False):
        self.host = host
        self.port = port
        self.password = password
        self.nokey = nokey
        self.power_state = "standby"
        self.server = None

    async def start(self):
        self.server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )

    async def _handle_client(self, reader, writer):
        # Send challenge or NOKEY
        if self.nokey:
            writer.write(b"NOKEY\r\n")
        else:
            challenge = secrets.token_hex(8)
            writer.write(f"{challenge}\r\n".encode())
            await writer.drain()

            # Read and validate auth
            auth_line = await reader.readline()
            expected = hashlib.sha256(
                (challenge + self.password).encode()
            ).hexdigest()
            if auth_line.decode().strip() != expected:
                writer.write(b"err_auth\r\n")
                writer.close()
                return
            writer.write(b"ok\r\n")

        await writer.drain()

        # Read and process command
        cmd_line = await reader.readline()
        response = self._process_command(cmd_line.decode().strip())
        writer.write(f"{response}\r\n".encode())
        await writer.drain()
        writer.close()
```

### Pytest Fixture Pattern

```python
@pytest.fixture
async def mock_projector():
    server = MockProjector(port=0)  # OS-assigned port
    await server.start()
    port = server.server.sockets[0].getsockname()[1]
    yield server, port
    server.server.close()
    await server.server.wait_closed()
```

Using `port=0` lets the OS assign an available port, avoiding conflicts in parallel tests.

## 5. Testing Strategy

### Test Categories for Phase 1

1. **Config tests** (unit, no I/O):
   - Load valid YAML, verify all fields populate dataclasses correctly
   - Load YAML with missing required fields, verify clear error message
   - Load YAML with defaults, verify defaults applied
   - Load malformed YAML, verify rejection
   - Load YAML with extra unknown fields, verify graceful handling

2. **ADCP client tests** (integration with mock server):
   - Connect + SHA256 auth + send command + receive "ok"
   - Connect + NOKEY mode + send command + receive "ok"
   - Auth failure (wrong password) → `AuthError`
   - Unknown command → `CommandError`
   - Invalid value → `ValueError`
   - Connection refused → `ConnectionError` with retry
   - Connection timeout → `ConnectionError` with retry
   - Retry succeeds on second attempt (mock refuses first, accepts second)

3. **Mock server tests** (verify mock behavior):
   - Serves challenge in auth mode
   - Serves NOKEY in nokey mode
   - Validates correct auth hash
   - Rejects incorrect auth hash
   - Processes known commands
   - Returns error for unknown commands

### pytest-asyncio Setup

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

This avoids needing `@pytest.mark.asyncio` on every test function.

## 6. Module Structure

Recommended package layout for Phase 1:

```
src/projector_bridge/
    __init__.py
    __main__.py          # CLI entry point (stub in Phase 1)
    config.py            # YAML loading + dataclass definitions
    adcp.py              # ADCP client (connect, auth, send, parse)
    errors.py            # Typed exception hierarchy
    mock_server.py       # Mock ADCP projector server

tests/
    conftest.py          # Shared fixtures (mock_projector)
    test_config.py       # Config loading/validation tests
    test_adcp.py         # ADCP client integration tests
    test_mock_server.py  # Mock server behavior tests
```

## 7. Phase-Specific Risks

### From PITFALLS.md — Relevant to Phase 1

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Pitfall 2:** Auth concatenation order | Cannot authenticate, zero commands work | Use `challenge + password` order. Unit test with known vectors. |
| **Pitfall 8:** Concurrent connection serialization | Commands lost or errored | Design async lock/queue from day one in the client |
| **Pitfall 3:** Projector unreachable in standby | Power-on command fails | Handle connection refused with specific error message. Not a Phase 1 blocker (mock server doesn't have this issue) but the error type must exist |
| **Pitfall 12:** Commands during power transitions | Commands ignored/errored | Not Phase 1 scope, but the error parsing must handle `err_inactive` response |

### Phase 1 Specific Risks

1. **ADCP response parsing edge cases** — The protocol may have responses we haven't seen. The parser should handle unexpected responses gracefully (log + return raw string) rather than crashing.

2. **Mock server fidelity** — If the mock doesn't accurately simulate the protocol, tests pass but real projector fails. Mitigate by matching the kennymc-c reference implementation's behavior exactly.

3. **Config validation completeness** — Under-validation leads to runtime crashes. Over-validation leads to user frustration. Validate only what matters: required fields exist, types are correct, values are in sensible ranges.

## 8. Reference Implementation Analysis

### kennymc-c/ucr-integration-sonyADCP (Primary Reference)

Key patterns to replicate:
- Auth flow: connect → read challenge → SHA256(challenge + password) → send hash → read ok/err
- Command format: `command_name "parameter"` with space separator and quoted parameter
- Error handling: parse response prefix to determine error type
- NOKEY detection: check if challenge line equals "NOKEY"

### Key Differences from Reference

- Reference is synchronous (blocking sockets); we use asyncio
- Reference maintains persistent connection; we use open-per-command
- Reference is in a UCR integration context; we are standalone
- Reference doesn't have retry logic; we add exponential backoff

## Validation Architecture

### Verification Points for Phase 1

1. **SHA256 auth verification** — Known challenge + known password → expected hash (deterministic test vector)
2. **NOKEY path verification** — Mock in NOKEY mode → client skips auth → command succeeds
3. **Error type mapping verification** — Each ADCP error prefix → correct Python exception type
4. **Config round-trip verification** — Write YAML → load → verify all dataclass fields match
5. **Retry behavior verification** — Mock refuses N-1 times → client retries → succeeds on attempt N
6. **Timeout verification** — Mock delays beyond timeout → client raises within expected timeframe

## RESEARCH COMPLETE
