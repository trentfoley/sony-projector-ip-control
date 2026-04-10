# Phase 1: ADCP Client, Config, and Mock Server - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Project foundation: YAML config system with dataclass validation, async TCP ADCP client with SHA256 challenge-response authentication, and a mock ADCP server for development/testing. This phase delivers the ability to send ADCP commands to a projector (or mock) from the command line, with all settings driven by config.

Requirements: MAP-01, ADCP-01, ADCP-02, ADCP-03, ADCP-04, DEV-02

</domain>

<decisions>
## Implementation Decisions

### Config structure
- **D-01:** Flat top-level sections — `projector`, `mappings`, `ir` as top-level YAML keys. No deep nesting.
- **D-02:** Explicit config location only — `--config` CLI flag or `./config.yaml`. No magic search path cascade.
- **D-03:** Scancode-keyed mappings — scancode (hex string) is the dict key, value is `{command, repeat, description}`. Enables O(1) lookup.
- **D-04:** Required essentials — `projector.host` and `projector.password` are required fields. Everything else has sensible defaults (port: 53595, timeout: 5s, retries: 3, etc.). Fail fast with clear error if essentials are missing.

### ADCP protocol handling
- **D-05:** TCP timeouts — 5 second connect timeout, 3 second read timeout. Generous enough for projector waking from standby.
- **D-06:** Retry strategy — Exponential backoff: 200ms, 400ms (3 total attempts). Retries on transient connection failures only, not on auth or command errors.
- **D-07:** Error model — Typed exceptions (`AuthError`, `CommandError`, `ValueError`, `InactiveError`, `ConnectionError`). Caller catches what it cares about. Each maps to an ADCP error code.
- **D-08:** Connection lifecycle — Open-per-command: connect → read challenge → auth → send command → read response → close. No persistent connections (projector has 60s idle timeout).
- **D-09:** Protocol format — ASCII over TCP, `\r\n` line termination, port 53595. Auth is SHA256(`challenge + password`).hexdigest(). NOKEY mode skips auth when projector has auth disabled.

### Claude's Discretion
- Mock server implementation details (standalone script vs pytest fixture — both are fine)
- Exact dataclass field names and validation approach
- Logging format and verbosity levels
- Module file naming within the package

</decisions>

<specifics>
## Specific Ideas

- Reference implementations to study: kennymc-c/ucr-integration-sonyADCP (most complete, has SHA256 auth) and tokyotexture/homeassistant-custom-components (simpler reference)
- ADCP protocol: connect on TCP:53595, server sends challenge string, client responds with `sha256(challenge + password).hexdigest()`, then sends commands as ASCII lines
- NOKEY mode: when projector auth is disabled, server sends "NOKEY" instead of a challenge — client skips auth and sends commands directly
- ADCP responses: `"ok"` for success, quoted values for queries (`power_status ?` → `"standby"`), typed error prefixes for failures
- Password default on VPL-XW5000ES is "Projector" (case-sensitive)

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### ADCP protocol
- `.planning/research/FEATURES.md` — Feature landscape with ADCP auth flow, command format, error codes, and mock server scope
- `.planning/research/STACK.md` — Technology stack decisions: asyncio, hashlib for SHA256, dataclasses for config
- `.planning/research/PITFALLS.md` — Known risks and failure modes for ADCP communication

### External references (not in repo — research agents should consult)
- kennymc-c/ucr-integration-sonyADCP on GitHub — Most complete open-source ADCP implementation with SHA256 auth
- Sony VPL-XW5000ES ADCP Settings help page — Port 53595, auth, 60s timeout, IP restriction

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code

### Established Patterns
- None yet — this phase establishes the foundational patterns for the project

### Integration Points
- Config system will be consumed by Phase 2 (Command Mapper) and Phase 3 (IR Listener)
- ADCP client will be called by Phase 2's command mapper for sending translated commands
- Mock server will be used in Phase 2 and Phase 3 testing

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-adcp-client-config-and-mock-server*
*Context gathered: 2026-04-10*
