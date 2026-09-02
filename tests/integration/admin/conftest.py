"""The admin's own contour: the production assembly over a real database.

Django is configured once per session from a ``Config`` the fixture builds by
hand (§14.5.2), through the very function the admin process uses — so a broken
app registry, URL conf or middleware chain reddens here.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator

import django
import pytest
from django.conf import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from memiro.adapters.db.config import DbConfig
from memiro.application.submit_inquiry import LegalConfig
from memiro.bootstrap.config_loader import Config
from memiro.bootstrap.django_admin.assembly import admin_settings
from memiro.presentation.django_admin.config import PASSWORD_ENV, USERNAME_ENV, AdminConfig
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


@pytest.fixture(scope="session")
def owner_credentials() -> Iterator[None]:
    """Put the owner's credentials where ``ensure_superuser`` reads them, and take them back."""
    previous = {name: os.environ.get(name) for name in (USERNAME_ENV, PASSWORD_ENV)}
    os.environ[USERNAME_ENV] = OWNER_USERNAME
    os.environ[PASSWORD_ENV] = OWNER_PASSWORD

    yield

    for name, value in previous.items():
        if value is None:
            del os.environ[name]
        else:
            os.environ[name] = value


@pytest.fixture(scope="session")
async def admin_site(
    postgres: PostgresContainer,
    admin_engine: AsyncEngine,
    template_database: str,
    owner_credentials: None,  # noqa: ARG001
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncIterator[None]:
    """Bring Django up on a clone of the migrated database, with the owner's account."""
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

    call_command("migrate", "--no-input", verbosity=0)
    call_command("ensure_superuser", verbosity=0)


def _close_connections() -> None:
    """Hand back the connections Django opened, before the database is dropped."""
    from django.db import connections  # noqa: PLC0415

    connections.close_all()
