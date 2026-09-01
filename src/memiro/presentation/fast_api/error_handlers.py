from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import DBAPIError, IntegrityError

from memiro.adapters.db.errors import LOCK_NOT_AVAILABLE, RETRYABLE_VIOLATIONS, LockTimeoutError, sqlstate_of
from memiro.application.errors.catalog import (
    AttributeValueNotFoundError,
    CategoryNotFoundError,
    ProductNotFoundError,
    VariantNotFoundError,
)
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.entities.errors.attribute import InvalidFactorRateError
from memiro.entities.errors.inquiry import (
    ConsentRequiredError,
    EmptyInquiryError,
    InquirySourceNotAcceptedError,
    InvalidInquiryContentsError,
)
from memiro.entities.errors.measure import EmptyDimensionsError, NegativeMeasureError
from memiro.entities.errors.pricing import DuplicateSizeSurchargeError, InvalidSurchargeFactorError
from memiro.entities.errors.product import (
    DuplicateVariantError,
    InvalidQuantityError,
    InvalidVariantConfigurationError,
    InvalidVariantSortOrderError,
)
from memiro_common.errors import AppError
from memiro_common.logger import Logger

VALIDATION_ERROR_CODE = "VALIDATION_ERROR"
INTERNAL_ERROR_CODE = "INTERNAL_ERROR"
CONCURRENT_CHANGE_CODE = "CONCURRENT_CHANGE"

# The flat table keyed by exact type: a miss is a code defect, not a 500 by
# design, and it is logged as one. Its human mirror is docs/errors/.
ERROR_STATUSES: dict[type[AppError], int] = {
    CategoryNotFoundError: status.HTTP_404_NOT_FOUND,
    ProductNotFoundError: status.HTTP_404_NOT_FOUND,
    VariantNotFoundError: status.HTTP_404_NOT_FOUND,
    AttributeValueNotFoundError: status.HTTP_404_NOT_FOUND,
    PricingSettingsNotFoundError: status.HTTP_404_NOT_FOUND,
    InvalidFactorRateError: status.HTTP_400_BAD_REQUEST,
    NegativeMeasureError: status.HTTP_400_BAD_REQUEST,
    EmptyDimensionsError: status.HTTP_400_BAD_REQUEST,
    InvalidSurchargeFactorError: status.HTTP_400_BAD_REQUEST,
    DuplicateSizeSurchargeError: status.HTTP_400_BAD_REQUEST,
    InvalidVariantConfigurationError: status.HTTP_400_BAD_REQUEST,
    InvalidVariantSortOrderError: status.HTTP_400_BAD_REQUEST,
    InvalidQuantityError: status.HTTP_400_BAD_REQUEST,
    DuplicateVariantError: status.HTTP_409_CONFLICT,
    ConsentRequiredError: status.HTTP_400_BAD_REQUEST,
    EmptyInquiryError: status.HTTP_400_BAD_REQUEST,
    InquirySourceNotAcceptedError: status.HTTP_400_BAD_REQUEST,
    InvalidInquiryContentsError: status.HTTP_400_BAD_REQUEST,
    LockTimeoutError: status.HTTP_429_TOO_MANY_REQUESTS,
}

logger: Logger = structlog.get_logger(__name__)


class ErrorResponse(BaseModel):
    """The one response shape of every failure: a machine code, a message and its context."""

    code: str
    message: str
    meta: dict[str, Any] | None = None


async def _handle_app_error(_request: Request, exc: Exception) -> JSONResponse:
    """Map an expected business failure onto its status through the table."""
    if not isinstance(exc, AppError):
        # The handler is registered on AppError; anything else here means the
        # registration was changed without this code (§12.3).
        msg = f"The application error handler was given a {type(exc).__name__}"
        raise TypeError(msg)
    code = type(exc).code
    http_status = ERROR_STATUSES.get(type(exc))
    if http_status is None:
        logger.critical("Error is missing from the HTTP mapping table", code=code)
        return _response(status.HTTP_500_INTERNAL_SERVER_ERROR, INTERNAL_ERROR_CODE, "Internal error")
    # Refusals are 4xx by construction, so they are logged at info; the
    # threshold's other half is the critical above (§10.3).
    logger.info("Request refused", code=code, status=http_status)
    return _response(http_status, code, exc.message, exc.meta)


async def _handle_validation_error(_request: Request, exc: Exception) -> JSONResponse:
    """Give FastAPI's own validation failure the same body as every other error."""
    return _response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        VALIDATION_ERROR_CODE,
        "Request validation failed",
        {"fields": _invalid_fields(exc)},
    )


def _invalid_fields(exc: Exception) -> list[str]:
    """Name the fields pydantic refused, in the dotted form the frontend reads."""
    if not isinstance(exc, RequestValidationError):
        return []
    fields: list[str] = []
    for error in exc.errors():
        location: Any = error.get("loc", ())
        fields.append(".".join(str(part) for part in location))
    return fields


async def _handle_integrity_error(request: Request, exc: Exception) -> JSONResponse:
    """Answer a race lost on a database invariant with an honest retry (§8.7).

    Only a uniqueness or exclusion failure is a race. A broken reference or a
    failed check is a defect, and answering it "retry the request" would leave
    the client looping on a 429 forever while nothing in monitoring fires.
    """
    if sqlstate_of(exc) not in RETRYABLE_VIOLATIONS:
        return await _handle_unexpected_error(request, exc)
    logger.info("Request lost a database race", error=type(exc).__name__, status=status.HTTP_429_TOO_MANY_REQUESTS)
    return _response(
        status.HTTP_429_TOO_MANY_REQUESTS,
        CONCURRENT_CHANGE_CODE,
        "Concurrent change, retry the request",
    )


async def _handle_dbapi_error(request: Request, exc: Exception) -> JSONResponse:
    """Answer a lock refused anywhere — not only in the gateway — with the retry it deserves.

    ``SAProductGateway`` translates the lock it takes itself, but the same wait
    is refused from ``flush`` and ``commit`` too, and there the driver failure
    arrives here as a plain ``DBAPIError``.
    """
    if sqlstate_of(exc) != LOCK_NOT_AVAILABLE:
        return await _handle_unexpected_error(request, exc)
    return await _handle_app_error(request, LockTimeoutError())


async def _handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    """Give a defect the same body as every refusal — the client parses one shape, always."""
    # The handler runs while the exception is being handled, so the traceback
    # is attached; ruff cannot see that from the signature alone.
    logger.exception("Request failed with an unexpected error", error=type(exc).__name__)  # noqa: LOG004
    return _response(status.HTTP_500_INTERNAL_SERVER_ERROR, INTERNAL_ERROR_CODE, "Internal error")


def _response(http_status: int, code: str, message: str, meta: dict[str, Any] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content=ErrorResponse(code=code, message=message, meta=meta).model_dump(mode="json"),
    )


def setup_error_handlers(app: FastAPI) -> None:
    """Install the global handlers that turn every exception into the one response shape (§10.3)."""
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(IntegrityError, _handle_integrity_error)
    app.add_exception_handler(DBAPIError, _handle_dbapi_error)
    # The catch-all is registered last and is the reason a deliberate
    # RuntimeError from the domain still leaves as {code, message, meta}
    # rather than as the framework's plain-text page (§10.3).
    app.add_exception_handler(Exception, _handle_unexpected_error)
