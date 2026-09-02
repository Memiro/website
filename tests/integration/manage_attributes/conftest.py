import pytest
from dishka import AsyncContainer
from fastapi import FastAPI


@pytest.fixture
def container(app: FastAPI) -> AsyncContainer:
    """Hand over the container the app assembled; each command opens its own REQUEST scope from it."""
    container: AsyncContainer = app.state.dishka_container
    return container
