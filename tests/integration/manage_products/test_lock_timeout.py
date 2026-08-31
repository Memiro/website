from dataclasses import replace

import pytest
from dishka import AsyncContainer
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.adapters.db.errors import LockTimeoutError
from memiro.application.manage_products import AddVariant, AddVariantForm
from memiro.bootstrap.config_loader import Config
from tests.common.factory.catalog import PRODUCT

pytestmark = pytest.mark.usefixtures("catalog")

# Short enough to keep the test fast, long enough not to fire on a healthy lock.
LOCK_TIMEOUT_MS = 250


@pytest.fixture
def config(config: Config) -> Config:
    """Shorten the lock wait so a held aggregate lock is refused within the test."""
    return replace(config, db=replace(config.db, lock_timeout_ms=LOCK_TIMEOUT_MS))


async def _add(container: AsyncContainer) -> None:
    """Execute one add in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(AddVariant)
        await interactor.execute(
            PRODUCT,
            AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0),
        )


async def test_a_command_asks_for_a_retry_when_the_aggregate_stays_locked(
    app: FastAPI,
    engine: AsyncEngine,
) -> None:
    """A lock held by a competitor is refused with LOCK_TIMEOUT."""
    container: AsyncContainer = app.state.dishka_container

    async with engine.connect() as competitor:
        await competitor.execute(
            text("SELECT id FROM products WHERE id = :product_id FOR UPDATE"),
            {"product_id": PRODUCT},
        )

        with pytest.raises(LockTimeoutError):
            await _add(container)
