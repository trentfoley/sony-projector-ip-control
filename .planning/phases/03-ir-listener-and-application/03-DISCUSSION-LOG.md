# Phase 3: IR Listener and Application - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-09
**Phase:** 03-ir-listener-and-application
**Areas discussed:** Discover mode output, CLI & entry point, Device detection & recovery, Logging defaults

---

## Discover mode output

| Option | Description | Selected |
|--------|-------------|----------|
| Scancode only | Clean, one value per line: `0x010` | |
| Scancode + key name | `0x010 KEY_VOLUMEUP` — both config key and kernel mapping | ✓ |
| Verbose | Full debug info: scancode + key name + event value + device name | |

**User's choice:** Scancode + key name
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Key-down only | One line per press, clean output | ✓ |
| Key-down + repeats | Shows repeat behavior, marks repeats with `(repeat)` tag | |
| You decide | | |

**User's choice:** Key-down only
**Notes:** None

---

## CLI & entry point

| Option | Description | Selected |
|--------|-------------|----------|
| Console script | `projector-bridge` via pyproject.toml `[project.scripts]` | |
| Module invocation | `python -m projector_bridge` via `__main__.py` | |
| Both | Console script + module invocation, same main function | ✓ |

**User's choice:** Both
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Just those two | `--config PATH` and `--discover` only | |
| Add --log-level | `--config`, `--discover`, `--log-level` | |
| Add --log-level and --version | All above plus `--version` | ✓ |

**User's choice:** Add --log-level and --version
**Notes:** None

---

## Device detection & recovery

| Option | Description | Selected |
|--------|-------------|----------|
| Fail immediately | Log error and exit. Let systemd retry. | |
| Poll with timeout | Retry every 2-3s for up to 30s, then fail | ✓ |
| Poll indefinitely | Keep retrying forever | |

**User's choice:** Poll with timeout
**Notes:** Handles slow device initialization after boot

| Option | Description | Selected |
|--------|-------------|----------|
| Exit cleanly | Log error, shut down, let systemd restart | ✓ |
| Retry reconnect | Re-find device with same poll logic, resume | |
| You decide | | |

**User's choice:** Exit cleanly
**Notes:** None

---

## Logging defaults

| Option | Description | Selected |
|--------|-------------|----------|
| WARNING | Silent unless something goes wrong | |
| INFO | Logs each ADCP command sent + unknown scancodes | ✓ |
| You decide | | |

**User's choice:** INFO
**Notes:** Good visibility for passively discovering unmapped buttons

| Option | Description | Selected |
|--------|-------------|----------|
| Plain text | Human-readable timestamps, easy to scan in journalctl | ✓ |
| Structured JSON | Machine-parseable JSON lines | |
| You decide | | |

**User's choice:** Plain text
**Notes:** JSON logging is v2 scope (REL-02). No custom log rotation — systemd journald handles it. User has 32GB SD card, systemd defaults are sufficient.

---

## Claude's Discretion

- Internal module structure (listener.py, main.py, __main__.py)
- Signal handler implementation details
- evdev device enumeration approach
- Whether discover mode reuses the listener class or is a standalone loop

## Deferred Ideas

None — discussion stayed within phase scope.
