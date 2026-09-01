import json
from typing import Any

from fastapi import FastAPI, Request, status
from sqlalchemy.exc import DBAPIError, IntegrityError

from memiro.adapters.db.errors import LOCK_NOT_AVAILABLE, UNIQUE_VIOLATION, LockTimeoutError
from memiro.presentation.fast_api.error_handlers import CONCURRENT_CHANGE_CODE, setup_error_handlers
from memiro_common.errors import AppError

REQUEST = Request({"type": "http", "method": "POST", "path": "/", "headers": []})


def _handlers() -> dict[Any, Any]:
    """Install the production handlers and hand back the registered table."""
    app = FastAPI()
    setup_error_handlers(app)
    return app.exception_handlers


def _driver_error(sqlstate: str) -> Exception:
    """Build the driver exception SQLAlchemy wraps, carrying the SQLSTATE asyncpg copies over."""
    error = Exception("driver failure")
    error.sqlstate = sqlstate  # type: ignore[attr-defined]
    return error


async def test_a_lost_database_race_asks_the_client_to_retry() -> None:
    """A unique-constraint violation leaves as 429 CONCURRENT_CHANGE."""
    handler = _handlers()[IntegrityError]

    response = await handler(REQUEST, IntegrityError("INSERT", (), _driver_error(UNIQUE_VIOLATION)))

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


async def test_a_broken_reference_is_a_defect_and_not_a_retry() -> None:
    """A foreign-key violation no retry can fix leaves as 500, not as 429 "retry the request"."""
    handler = _handlers()[IntegrityError]

    response = await handler(REQUEST, IntegrityError("INSERT", (), _driver_error("23503")))

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert json.loads(response.body)["code"] == "INTERNAL_ERROR"


async def test_a_lock_refused_outside_the_gateway_still_asks_the_client_to_retry() -> None:
    """A lock timeout surfacing from flush or commit leaves as 429 LOCK_TIMEOUT, not as 500."""
    handler = _handlers()[DBAPIError]

    response = await handler(REQUEST, DBAPIError("UPDATE", (), _driver_error(LOCK_NOT_AVAILABLE)))

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert json.loads(response.body)["code"] == "LOCK_TIMEOUT"


async def test_any_other_driver_failure_stays_a_defect() -> None:
    """A driver failure that is not a refused lock keeps its 500: it is nobody's race."""
    handler = _handlers()[DBAPIError]

    response = await handler(REQUEST, DBAPIError("UPDATE", (), _driver_error("08006")))

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert json.loads(response.body)["code"] == "INTERNAL_ERROR"
