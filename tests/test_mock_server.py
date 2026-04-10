"""Tests for the mock ADCP projector server."""

import pytest

from projector_bridge.adcp import send_command
from projector_bridge.config import ProjectorConfig
from projector_bridge.errors import AuthError, CommandError
from projector_bridge.mock_server import MockProjector, run_standalone


@pytest.fixture
async def mock_server():
    """Start a MockProjector on a random port, yield (mock, config), then stop."""
    mock = MockProjector(port=0)
    await mock.start()
    config = ProjectorConfig(
        host="127.0.0.1",
        port=mock.get_port(),
        password="Projector",
        timeout_connect=2.0,
        timeout_read=2.0,
    )
    yield mock, config
    await mock.stop()


@pytest.fixture
async def mock_nokey_server():
    """Start a MockProjector in NOKEY mode."""
    mock = MockProjector(port=0, nokey=True)
    await mock.start()
    config = ProjectorConfig(
        host="127.0.0.1",
        port=mock.get_port(),
        password="",
        timeout_connect=2.0,
        timeout_read=2.0,
    )
    yield mock, config
    await mock.stop()


async def test_mock_sha256_auth_accepts_correct_hash(mock_server):
    mock, config = mock_server
    result = await send_command(config, 'power "on"')
    assert result == "ok"
    assert 'power "on"' in mock.commands_received


async def test_mock_nokey_mode(mock_nokey_server):
    mock, config = mock_nokey_server
    result = await send_command(config, 'power "on"')
    assert result == "ok"


async def test_mock_rejects_wrong_password(mock_server):
    mock, config = mock_server
    bad_config = ProjectorConfig(
        host=config.host,
        port=config.port,
        password="wrong",
        timeout_connect=2.0,
        timeout_read=2.0,
    )
    with pytest.raises(AuthError):
        await send_command(bad_config, 'power "on"')


async def test_mock_power_state_tracking(mock_server):
    mock, config = mock_server

    result = await send_command(config, 'power "on"')
    assert result == "ok"

    result = await send_command(config, "power_status ?")
    assert result == "on"

    result = await send_command(config, 'power "off"')
    assert result == "ok"

    result = await send_command(config, "power_status ?")
    assert result == "standby"


async def test_mock_unknown_command(mock_server):
    mock, config = mock_server
    with pytest.raises(CommandError):
        await send_command(config, 'nonexistent "foo"')


def test_mock_binds_to_localhost_by_default():
    mock = MockProjector()
    assert mock.host == "127.0.0.1"


def test_mock_standalone_parseable():
    assert callable(run_standalone)
