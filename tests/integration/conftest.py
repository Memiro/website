import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
from asgi_lifespan import LifespanManager
from dishka import AsyncContainer
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from memiro.adapters.db.config import DbConfig
from memiro.adapters.db.migrations import apply_migrations
from memiro.application.submit_inquiry.config import LegalConfig
from memiro.bootstrap.config_loader import Config
from memiro.bootstrap.fast_api import create_app
from memiro_common.observability.config import ObservabilityConfig
from tests.integration.api_client import ApiClient
from tests.integration.prime import prime_dictionary, prime_pricing_settings

TEMPLATE_DATABASE = "memiro_template"


def _db_config(postgres: PostgresContainer, database: str) -> DbConfig:
    return DbConfig(
        host=postgres.get_container_host_ip(),
        port=int(postgres.get_exposed_port(5432)),
        user=postgres.username,
        password=postgres.password,
        database=database,
    )


@pytest.fixture(scope="session")
def postgres() -> Iterator[PostgresContainer]:
    """One Postgres container per test session (one set per xdist worker)."""
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as container:
        yield container


@pytest.fixture(scope="session")
async def admin_engine(postgres: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    """AUTOCOMMIT engine on the maintenance database for CREATE/DROP DATABASE."""
    engine = create_async_engine(
        _db_config(postgres, postgres.dbname).url,
        isolation_level="AUTOCOMMIT",
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def template_database(postgres: PostgresContainer, admin_engine: AsyncEngine) -> str:
    """Create the template database and run migrations into it once (§14.5.1)."""
    async with admin_engine.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{TEMPLATE_DATABASE}"'))
    # apply_migrations drives alembic through its own asyncio.run — off-loop.
    await asyncio.to_thread(apply_migrations, _db_config(postgres, TEMPLATE_DATABASE).url)
    return TEMPLATE_DATABASE


@pytest.fixture
async def database_name(
    admin_engine: AsyncEngine,
    template_database: str,
) -> AsyncIterator[str]:
    """Clone a fresh database from the template; drop it after the test."""
    name = f"test_{uuid.uuid4().hex}"
    async with admin_engine.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{name}" TEMPLATE "{template_database}"'))
    yield name
    async with admin_engine.connect() as connection:
        await connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))


@pytest.fixture
def config(postgres: PostgresContainer, database_name: str) -> Config:
    """Test config built by hand — never calls ``Config.load()`` (§14.5.2)."""
    return Config(
        db=_db_config(postgres, database_name),
        observability=ObservabilityConfig(enabled=False, log_level="WARNING"),
        legal=LegalConfig(consent_version="2026-08-31"),
    )


@pytest.fixture
async def app(config: Config) -> AsyncIterator[FastAPI]:
    """Assemble the app via the production ``create_app``; the lifespan really runs."""
    application = create_app(config)
    async with LifespanManager(application):
        yield application


@pytest.fixture
async def engine(app: FastAPI) -> AsyncEngine:
    """Take the app's own engine out of its production container."""
    container: AsyncContainer = app.state.dishka_container
    return await container.get(AsyncEngine)


@pytest.fixture
async def dictionary(engine: AsyncEngine) -> None:
    """Put the demo dictionary and canonical product into the database."""
    await prime_dictionary(engine)


@pytest.fixture
async def catalog(engine: AsyncEngine) -> None:
    """Put the priceable demo catalogue into the database."""
    await prime_dictionary(engine)
    await prime_pricing_settings(engine)


@pytest.fixture
async def api_client(app: FastAPI) -> AsyncIterator[ApiClient]:
    """Typed HTTP client over the in-process app."""
    async with ApiClient(app) as client:
        yield client
