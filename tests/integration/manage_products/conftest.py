from collections.abc import AsyncIterator

import pytest
from dishka import AsyncContainer
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.prime import prime_dictionary, prime_pricing_settings


@pytest.fixture
async def engine(app: FastAPI) -> AsyncEngine:
    """Take the app's own engine out of its production container."""
    container: AsyncContainer = app.state.dishka_container
    return await container.get(AsyncEngine)


@pytest.fixture
async def dictionary(engine: AsyncEngine) -> None:
    """Put the demo dictionary and product into the isolated database."""
    await prime_dictionary(engine)


@pytest.fixture
async def catalog(engine: AsyncEngine) -> None:
    """Put the priceable demo catalogue in the isolated database."""
    await prime_dictionary(engine)
    await prime_pricing_settings(engine)


@pytest.fixture
async def request_container(app: FastAPI) -> AsyncIterator[AsyncContainer]:
    """Open a real REQUEST scope from the production dishka container."""
    container: AsyncContainer = app.state.dishka_container
    async with container() as request:
        yield request
