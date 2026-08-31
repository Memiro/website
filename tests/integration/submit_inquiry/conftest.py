from collections.abc import AsyncIterator

import pytest
from dishka import AsyncContainer
from fastapi import FastAPI


@pytest.fixture
async def request_container(app: FastAPI) -> AsyncIterator[AsyncContainer]:
    """Open a real REQUEST scope from the production dishka container."""
    container: AsyncContainer = app.state.dishka_container
    async with container() as request:
        yield request
