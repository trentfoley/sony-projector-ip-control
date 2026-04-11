"""Async ADCP TCP client with SHA256 auth and retry."""

import asyncio
import hashlib
import logging

from projector_bridge.config import ProjectorConfig
from projector_bridge.errors import (
    AuthError,
    CommandError,
    CommandValueError,
    ConnectionError,
    InactiveError,
)

log = logging.getLogger(__name__)

_ERROR_MAP: dict[str, type[Exception]] = {
    "err_auth": AuthError,
    "err_cmd": CommandError,
    "err_val": CommandValueError,
    "err_option": CommandValueError,
    "err_inactive": InactiveError,
}


def parse_response(response: str) -> str:
    """Parse an ADCP response string, raising typed errors for error responses.

    Returns the response value on success:
    - "ok" for command acknowledgments
    - Unquoted value for query responses (e.g., '"standby"' -> 'standby')

    Raises:
        AuthError: for "err_auth"
        CommandError: for "err_cmd"
        CommandValueError: for "err_val"
        InactiveError: for "err_inactive"
    """
    for prefix, exc_type in _ERROR_MAP.items():
        if response == prefix:
            raise exc_type(
                {
                    "err_auth": "Authentication failed",
                    "err_cmd": "Unknown command",
                    "err_val": "Invalid parameter value",
                    "err_option": "Invalid option for this command",
                    "err_inactive": "Projector inactive (deep standby?)",
                }[prefix]
            )

    if response == "ok":
        return "ok"

    # Strip quotes from query responses like '"standby"'
    if response.startswith('"') and response.endswith('"'):
        return response[1:-1]

    # Unquoted values are normal for numeric/enum queries (e.g. brightness -> 50)
    return response


async def send_command(config: ProjectorConfig, command: str) -> str:
    """Send a single ADCP command over a new TCP connection.

    Opens a connection, performs SHA256 challenge-response auth (or skips
    for NOKEY mode), sends the command, and returns the parsed response.
    The connection is closed after each command (open-per-command model).
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(config.host, config.port),
            timeout=config.timeout_connect,
        )
    except (OSError, TimeoutError) as err:
        raise ConnectionError(
            f"Failed to connect to {config.host}:{config.port}: {err}"
        ) from err

    try:
        # Read challenge line
        try:
            challenge_line = await asyncio.wait_for(
                reader.readline(), timeout=config.timeout_read
            )
        except TimeoutError as err:
            raise ConnectionError("Timeout waiting for challenge from projector") from err

        challenge = challenge_line.decode("ascii").strip()
        if not challenge:
            raise ConnectionError("No challenge received from projector")

        # Authenticate if not NOKEY
        if challenge != "NOKEY":
            auth_hash = hashlib.sha256(
                (challenge + config.password).encode()
            ).hexdigest()
            writer.write(f"{auth_hash}\r\n".encode("ascii"))
            await writer.drain()

            try:
                auth_response_line = await asyncio.wait_for(
                    reader.readline(), timeout=config.timeout_read
                )
            except TimeoutError as err:
                raise ConnectionError("Timeout waiting for auth response") from err

            auth_response = auth_response_line.decode("ascii").strip()
            if auth_response != "ok":
                raise AuthError("Authentication failed")

        # Send command
        writer.write(f"{command}\r\n".encode("ascii"))
        await writer.drain()

        # Read command response
        try:
            response_line = await asyncio.wait_for(
                reader.readline(), timeout=config.timeout_read
            )
        except TimeoutError as err:
            raise ConnectionError("Timeout waiting for command response") from err

        return parse_response(response_line.decode("ascii").strip())
    finally:
        writer.close()
        await writer.wait_closed()


async def send_command_with_retry(config: ProjectorConfig, command: str) -> str:
    """Send an ADCP command with exponential backoff retry on connection failures.

    Only retries on ConnectionError (transient network issues).
    AuthError, CommandError, CommandValueError, and InactiveError propagate
    immediately since they are not transient.
    """
    delay = config.retry_delay
    for attempt in range(config.retries):
        try:
            return await send_command(config, command)
        except ConnectionError:
            if attempt == config.retries - 1:
                raise
            log.warning(
                "ADCP connection failed (attempt %d/%d), retrying in %.1fs",
                attempt + 1,
                config.retries,
                delay,
            )
            await asyncio.sleep(delay)
            delay *= 2
    # Should not be reached, but satisfies type checker
    raise ConnectionError("All retry attempts exhausted")  # pragma: no cover
