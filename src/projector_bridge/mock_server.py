"""Mock ADCP projector server for development and testing."""

import argparse
import asyncio
import hashlib
import hmac
import logging
import secrets

log = logging.getLogger(__name__)

# Known commands and their valid parameter patterns
_KNOWN_COMMANDS = {
    "power": {"on", "off"},
    "power_status": {"?"},
    "input": {"hdmi1", "hdmi2"},
    "key": None,  # any value accepted
    "blank": {"on", "off"},
}


class MockProjector:
    """Simulates a Sony ADCP projector for testing."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 53595,
        password: str = "Projector",
        nokey: bool = False,
    ):
        self.host = host
        self.port = port
        self.password = password
        self.nokey = nokey

        self.power_state: str = "standby"
        self.input_state: str = "hdmi1"
        self.commands_received: list[str] = []
        self.server: asyncio.Server | None = None

    async def start(self) -> None:
        """Start the mock ADCP TCP server."""
        self.server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )

    async def stop(self) -> None:
        """Stop the mock server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    def get_port(self) -> int:
        """Return the actual listening port (useful when started with port=0)."""
        assert self.server is not None
        return self.server.sockets[0].getsockname()[1]

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a single ADCP client connection."""
        try:
            # Send challenge or NOKEY
            if self.nokey:
                writer.write(b"NOKEY\r\n")
                await writer.drain()
            else:
                challenge = secrets.token_hex(8)
                writer.write(f"{challenge}\r\n".encode("ascii"))
                await writer.drain()

                # Read and validate auth hash
                auth_line = await reader.readline()
                if not auth_line:
                    return
                received_hash = auth_line.decode("ascii").strip()
                expected_hash = hashlib.sha256(
                    (challenge + self.password).encode()
                ).hexdigest()

                if hmac.compare_digest(received_hash, expected_hash):
                    writer.write(b"ok\r\n")
                else:
                    writer.write(b"err_auth\r\n")
                    await writer.drain()
                    return
                await writer.drain()

            # Read command
            cmd_line = await reader.readline()
            if not cmd_line:
                return
            command = cmd_line.decode("ascii").strip()
            self.commands_received.append(command)

            # Process and respond
            response = self._process_command(command)
            writer.write(f"{response}\r\n".encode("ascii"))
            await writer.drain()
        except Exception:
            log.exception("Error handling client")
        finally:
            writer.close()
            await writer.wait_closed()

    def _process_command(self, command: str) -> str:
        """Process an ADCP command and return the response string."""
        parts = command.split(None, 1)
        if not parts:
            return "err_cmd"

        cmd_name = parts[0]
        param = parts[1].strip('"') if len(parts) > 1 else ""

        if cmd_name not in _KNOWN_COMMANDS:
            return "err_cmd"

        valid_values = _KNOWN_COMMANDS[cmd_name]

        # Query handling
        if param == "?":
            if cmd_name == "power_status":
                return f'"{self.power_state}"'
            return "err_val"

        # Validate parameter if command has a fixed set
        if valid_values is not None and param not in valid_values:
            return "err_val"

        # Execute command
        if cmd_name == "power":
            self.power_state = "on" if param == "on" else "standby"
        elif cmd_name == "input":
            self.input_state = param

        return "ok"


async def run_standalone(
    host: str = "127.0.0.1",
    port: int = 53595,
    password: str = "Projector",
    nokey: bool = False,
) -> None:
    """Run the mock projector as a standalone server."""
    server = MockProjector(host=host, port=port, password=password, nokey=nokey)
    await server.start()
    print(f"Mock projector listening on {host}:{server.get_port()}")
    print(f"Auth mode: {'NOKEY' if nokey else 'SHA256'}")
    try:
        await asyncio.Event().wait()
    finally:
        await server.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock Sony ADCP projector server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=53595, help="Bind port")
    parser.add_argument("--password", default="Projector", help="Auth password")
    parser.add_argument("--nokey", action="store_true", help="Disable auth (NOKEY mode)")
    args = parser.parse_args()
    asyncio.run(
        run_standalone(
            host=args.host, port=args.port, password=args.password, nokey=args.nokey
        )
    )
