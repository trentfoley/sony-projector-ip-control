"""Tests for the ADCP client: auth, commands, parsing, and retry."""

import asyncio
import hashlib

import pytest

from projector_bridge.adcp import parse_response, send_command, send_command_with_retry
from projector_bridge.config import ProjectorConfig
from projector_bridge.errors import (
    AuthError,
    CommandError,
    CommandValueError,
    ConnectionError,
    InactiveError,
)


async def _run_mock_server(handler, host="127.0.0.1"):
    """Start a TCP server on an OS-assigned port, return (server, port)."""
    server = await asyncio.start_server(handler, host, 0)
    port = server.sockets[0].getsockname()[1]
    return server, port


def _make_config(port, password="Projector", **kwargs):
    """Build a ProjectorConfig pointing at localhost with given port."""
    return ProjectorConfig(
        host="127.0.0.1",
        port=port,
        password=password,
        timeout_connect=2.0,
        timeout_read=2.0,
        retries=kwargs.get("retries", 3),
        retry_delay=kwargs.get("retry_delay", 0.01),
    )


# --- parse_response tests ---


def test_parse_response_ok():
    assert parse_response("ok") == "ok"


@pytest.mark.parametrize(
    "response,exc_type",
    [
        ("err_auth", AuthError),
        ("err_cmd", CommandError),
        ("err_val", CommandValueError),
        ("err_inactive", InactiveError),
    ],
)
def test_parse_response_error_types(response, exc_type):
    with pytest.raises(exc_type):
        parse_response(response)


# --- send_command tests ---


async def test_send_command_with_sha256_auth():
    challenge = "testchallenge123"
    expected_hash = hashlib.sha256(
        (challenge + "Projector").encode()
    ).hexdigest()

    async def handler(reader, writer):
        writer.write(f"{challenge}\r\n".encode("ascii"))
        await writer.drain()
        # Read auth hash
        auth_line = await reader.readline()
        auth = auth_line.decode("ascii").strip()
        if auth == expected_hash:
            writer.write(b"ok\r\n")
        else:
            writer.write(b"err_auth\r\n")
        await writer.drain()
        # Read command
        await reader.readline()
        writer.write(b"ok\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server, port = await _run_mock_server(handler)
    async with server:
        config = _make_config(port)
        result = await send_command(config, 'power "on"')
        assert result == "ok"


async def test_send_command_nokey_mode():
    async def handler(reader, writer):
        writer.write(b"NOKEY\r\n")
        await writer.drain()
        # No auth exchange — read command directly
        await reader.readline()
        writer.write(b"ok\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server, port = await _run_mock_server(handler)
    async with server:
        config = _make_config(port)
        result = await send_command(config, 'power "on"')
        assert result == "ok"


async def test_send_command_auth_failure():
    async def handler(reader, writer):
        writer.write(b"somechallenge\r\n")
        await writer.drain()
        await reader.readline()  # read hash
        writer.write(b"err_auth\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server, port = await _run_mock_server(handler)
    async with server:
        config = _make_config(port, password="WrongPassword")
        with pytest.raises(AuthError):
            await send_command(config, 'power "on"')


async def test_send_command_unknown_command():
    async def handler(reader, writer):
        writer.write(b"NOKEY\r\n")
        await writer.drain()
        await reader.readline()
        writer.write(b"err_cmd\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server, port = await _run_mock_server(handler)
    async with server:
        config = _make_config(port)
        with pytest.raises(CommandError):
            await send_command(config, "bogus_command")


async def test_send_command_invalid_value():
    async def handler(reader, writer):
        writer.write(b"NOKEY\r\n")
        await writer.drain()
        await reader.readline()
        writer.write(b"err_val\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server, port = await _run_mock_server(handler)
    async with server:
        config = _make_config(port)
        with pytest.raises(CommandValueError):
            await send_command(config, 'power "invalid"')


async def test_send_command_inactive():
    async def handler(reader, writer):
        writer.write(b"NOKEY\r\n")
        await writer.drain()
        await reader.readline()
        writer.write(b"err_inactive\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server, port = await _run_mock_server(handler)
    async with server:
        config = _make_config(port)
        with pytest.raises(InactiveError):
            await send_command(config, 'power "on"')


async def test_send_command_query_response():
    async def handler(reader, writer):
        writer.write(b"NOKEY\r\n")
        await writer.drain()
        await reader.readline()
        writer.write(b'"standby"\r\n')
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server, port = await _run_mock_server(handler)
    async with server:
        config = _make_config(port)
        result = await send_command(config, "power_status ?")
        assert result == "standby"


async def test_send_command_connection_refused():
    # Port 1 is almost certainly not running an ADCP server
    config = _make_config(port=1, retries=1, retry_delay=0.01)
    with pytest.raises(ConnectionError):
        await send_command(config, 'power "on"')


# --- retry tests ---


async def test_retry_succeeds_on_second_attempt():
    attempt_count = 0

    async def handler(reader, writer):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            # First attempt: close immediately to simulate connection failure
            writer.close()
            await writer.wait_closed()
            return
        # Second attempt: succeed
        writer.write(b"NOKEY\r\n")
        await writer.drain()
        await reader.readline()
        writer.write(b"ok\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server, port = await _run_mock_server(handler)
    async with server:
        config = _make_config(port, retries=3, retry_delay=0.01)
        result = await send_command_with_retry(config, 'power "on"')
        assert result == "ok"
        assert attempt_count == 2


async def test_retry_exhausted():
    config = _make_config(port=1, retries=2, retry_delay=0.01)
    with pytest.raises(ConnectionError):
        await send_command_with_retry(config, 'power "on"')
