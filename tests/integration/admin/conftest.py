"""The admin's own contour: the production assembly over a real database.

Django is configured once per session from a ``Config`` the fixture builds by
hand (§14.5.2), through the very function the admin process uses — so a broken
app registry, URL conf or middleware chain reddens here.
"""

import asyncio
from collections.abc import AsyncIterator

import django
import pytest
from django.conf import settings
from django.test import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from memiro.adapters.db.config import DbConfig
from memiro.application.submit_inquiry import LegalConfig
from memiro.bootstrap.config_loader import Config
from memiro.bootstrap.django_admin.assembly import admin_settings
from memiro.presentation.django_admin.config import AdminConfig
from memiro.presentation.django_admin.credentials import OwnerCredentials
from memiro_common.observability.config import ObservabilityConfig
from tests.integration.prime import (
    prime_dictionary,
    prime_pricing_settings,
    prime_product_images,
    prime_size_surcharge,
)

ADMIN_DATABASE = "memiro_admin"
OWNER_USERNAME = "owner"
OWNER_PASSWORD = "owner-password"  # noqa: S105  # nosec B105  # a throwaway account in a throwaway database
# Handed to the production upsert directly: the environment is the deployment's
# way in, never the tests' (§14.5.2).
OWNER = OwnerCredentials(username=OWNER_USERNAME, password=OWNER_PASSWORD)


@pytest.fixture(scope="session")
async def admin_site(
    postgres: PostgresContainer,
    admin_engine: AsyncEngine,
    template_database: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncIterator[None]:
    """Bring Django up on a clone of the migrated database, with the owner's account.

    Never calls ``Config.load()``: the configuration is built by hand (§14.5.2).
    """
    async with admin_engine.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{ADMIN_DATABASE}" TEMPLATE "{template_database}"'))

    config = Config(
        db=DbConfig(
            host=postgres.get_container_host_ip(),
            port=int(postgres.get_exposed_port(5432)),
            user=postgres.username,
            password=postgres.password,
            database=ADMIN_DATABASE,
        ),
        observability=ObservabilityConfig(enabled=False, log_level="WARNING"),
        legal=LegalConfig(consent_version="2026-08-31"),
        admin=AdminConfig(
            secret_key="test-only-not-a-secret",  # noqa: S106  # nosec B106
            allowed_hosts=("testserver", "localhost"),
            static_root=str(tmp_path_factory.mktemp("admin-static")),
        ),
    )
    settings.configure(**admin_settings(config))
    django.setup()

    await asyncio.to_thread(_prepare_service_tables)

    yield

    await asyncio.to_thread(_close_connections)
    async with admin_engine.connect() as connection:
        await connection.execute(text(f'DROP DATABASE "{ADMIN_DATABASE}" WITH (FORCE)'))


@pytest.fixture
async def owner_client(admin_site: None) -> AsyncClient:  # noqa: ARG001
    """Sign an admin client in as the owner."""
    client = AsyncClient()
    await client.alogin(username=OWNER_USERNAME, password=OWNER_PASSWORD)

    return client


@pytest.fixture(scope="session")
def admin_database_url(postgres: PostgresContainer, admin_site: None) -> str:  # noqa: ARG001
    """Reflection URL of the very database the admin is looking at."""
    host = postgres.get_container_host_ip()
    port = postgres.get_exposed_port(5432)
    return f"postgresql+asyncpg://{postgres.username}:{postgres.password}@{host}:{port}/{ADMIN_DATABASE}"


@pytest.fixture(scope="session")
async def primed_catalog(admin_database_url: str) -> None:
    """Put the demo catalogue into the admin's database, child rows included."""
    engine = create_async_engine(admin_database_url)
    try:
        await prime_dictionary(engine)
        await prime_pricing_settings(engine)
        await prime_size_surcharge(engine)
        await prime_product_images(engine)
    finally:
        await engine.dispose()


def _prepare_service_tables() -> None:
    """Run Django's own migrations and create the owner, off the event loop."""
    # Imported here: the app registry may not be touched before django.setup(),
    # and that runs inside the fixture above.
    from django.core.management import call_command  # noqa: PLC0415

    from memiro.presentation.django_admin.management.commands.ensure_superuser import (  # noqa: PLC0415
        ensure_superuser,
    )

    call_command("migrate", "--no-input", verbosity=0)
    ensure_superuser(OWNER)


def _close_connections() -> None:
    """Hand back the connections Django opened, before the database is dropped."""
    from django.db import connections  # noqa: PLC0415

    connections.close_all()
