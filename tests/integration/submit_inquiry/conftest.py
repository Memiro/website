import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from email.parser import BytesParser
from email.policy import default

import pytest
from asgi_lifespan import LifespanManager
from dishka import AsyncContainer
from fastapi import FastAPI

from memiro.adapters.smtp.config import EmailConfig
from memiro.bootstrap.config_loader import Config
from memiro.bootstrap.fast_api import create_app
from tests.integration.api_client import ApiClient


@pytest.fixture
async def request_container(app: FastAPI) -> AsyncIterator[AsyncContainer]:
    """Open a real REQUEST scope from the production dishka container."""
    container: AsyncContainer = app.state.dishka_container
    async with container() as request:
        yield request


@pytest.fixture
async def smtp_server() -> AsyncIterator[tuple[int, list[str]]]:
    """Run a minimal SMTP peer that records the delivered message bodies."""
    received: list[str] = []

    async def receive(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(b"220 test SMTP\r\n")
        await writer.drain()
        lines: list[bytes] = []
        in_data = False
        while line := await reader.readline():
            if in_data:
                if line == b".\r\n":
                    received.append(BytesParser(policy=default).parsebytes(b"".join(lines)).get_content())
                    lines = []
                    in_data = False
                    writer.write(b"250 queued\r\n")
                else:
                    lines.append(line)
            elif line.upper().startswith(b"DATA"):
                in_data = True
                writer.write(b"354 message follows\r\n")
            elif line.upper().startswith(b"QUIT"):
                writer.write(b"221 bye\r\n")
                await writer.drain()
                break
            else:
                writer.write(b"250 ok\r\n")
            await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(receive, "127.0.0.1", 0)
    socket = server.sockets[0]
    port = int(socket.getsockname()[1])
    try:
        yield port, received
    finally:
        server.close()
        await server.wait_closed()


@pytest.fixture
async def notifying_api_client(
    config: Config,
    smtp_server: tuple[int, list[str]],
) -> AsyncIterator[ApiClient]:
    """Use the production app with its SMTP channel aimed at the local wire fake."""
    port, _ = smtp_server
    notifying_config = replace(
        config,
        email=EmailConfig(
            enabled=True,
            host="127.0.0.1",
            port=port,
            username="",
            from_address="site@example.test",
            manager_address="manager@example.test",
            timeout_seconds=1.0,
        ),
    )
    app = create_app(notifying_config)
    async with LifespanManager(app), ApiClient(app) as client:
        yield client


@pytest.fixture
async def silent_api_client(
    config: Config,
    smtp_server: tuple[int, list[str]],
) -> AsyncIterator[ApiClient]:
    """Use the production app whose SMTP channel is switched off but fully addressed."""
    port, _ = smtp_server
    silent_config = replace(
        config,
        email=EmailConfig(
            enabled=False,
            host="127.0.0.1",
            port=port,
            username="",
            from_address="site@example.test",
            manager_address="manager@example.test",
            timeout_seconds=1.0,
        ),
    )
    app = create_app(silent_config)
    async with LifespanManager(app), ApiClient(app) as client:
        yield client


@pytest.fixture
async def failing_app(config: Config, unused_tcp_port: int) -> AsyncIterator[FastAPI]:
    """Use the production app with an enabled SMTP channel that cannot connect."""
    failing_config = replace(
        config,
        email=EmailConfig(
            enabled=True,
            host="127.0.0.1",
            port=unused_tcp_port,
            from_address="site@example.test",
            manager_address="manager@example.test",
            timeout_seconds=1.0,
        ),
    )
    app = create_app(failing_config)
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def failing_api_client(failing_app: FastAPI) -> AsyncIterator[ApiClient]:
    """Send requests through the app whose external SMTP channel fails."""
    async with ApiClient(failing_app) as client:
        yield client


@pytest.fixture
async def empty_address_app(config: Config) -> AsyncIterator[FastAPI]:
    """Use the production app with its SMTP channel enabled but unaddressed."""
    empty_address_config = replace(
        config,
        email=EmailConfig(
            enabled=True,
            from_address="site@example.test",
            manager_address="",
        ),
    )
    app = create_app(empty_address_config)
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def empty_address_api_client(empty_address_app: FastAPI) -> AsyncIterator[ApiClient]:
    """Send requests through the app that must skip an unaddressed SMTP channel."""
    async with ApiClient(empty_address_app) as client:
        yield client
