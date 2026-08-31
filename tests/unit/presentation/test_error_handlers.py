import json
from typing import Any

from fastapi import FastAPI, Request, status
from sqlalchemy.exc import IntegrityError

from memiro.adapters.db.errors import LockTimeoutError
from memiro.presentation.fast_api.error_handlers import CONCURRENT_CHANGE_CODE, setup_error_handlers
from memiro_common.errors import AppError

REQUEST = Request({"type": "http", "method": "POST", "path": "/", "headers": []})


def _handlers() -> dict[Any, Any]:
    """Install the production handlers and hand back the registered table."""
    app = FastAPI()
    setup_error_handlers(app)
    return app.exception_handlers


async def test_a_lost_database_race_asks_the_client_to_retry() -> None:
    """A unique-constraint violation leaves as 429 CONCURRENT_CHANGE."""
    handler = _handlers()[IntegrityError]

    response = await handler(REQUEST, IntegrityError("INSERT", (), Exception("duplicate key")))

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert json.loads(response.body) == {
        "code": CONCURRENT_CHANGE_CODE,
        "message": "Concurrent change, retry the request",
        "meta": None,
    }


async def test_a_lock_timeout_asks_the_client_to_retry() -> None:
    """A refused aggregate lock leaves as 429 LOCK_TIMEOUT."""
    handler = _handlers()[AppError]

    response = await handler(REQUEST, LockTimeoutError())

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert json.loads(response.body) == {
        "code": "LOCK_TIMEOUT",
        "message": "The record is busy, retry the request",
        "meta": None,
    }
