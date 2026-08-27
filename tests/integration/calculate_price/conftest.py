import pytest
from dishka import AsyncContainer
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.prime import prime_dictionary, prime_pricing_settings


@pytest.fixture
async def engine(app: FastAPI) -> AsyncEngine:
    """Take the app's own engine out of its container — the tests write through it."""
    container: AsyncContainer = app.state.dishka_container
    return await container.get(AsyncEngine)


@pytest.fixture
async def dictionary(engine: AsyncEngine) -> None:
    """Put the demo dictionary and the canonical product into the database."""
    await prime_dictionary(engine)


@pytest.fixture
async def catalog(engine: AsyncEngine) -> None:
    """Put a priceable catalogue in place: the dictionary plus the pricing settings."""
    await prime_dictionary(engine)
    await prime_pricing_settings(engine)
