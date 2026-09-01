from typing import ClassVar

from memiro_common.errors import AppError, app_error

# Postgres reports a lock wait cut short by ``lock_timeout`` as lock_not_available.
LOCK_NOT_AVAILABLE = "55P03"

# The two integrity failures a second attempt can genuinely win. Every other
# one — a broken reference, a failed check, a missing value — is a defect that
# no retry fixes, and telling the client to retry would hide it forever.
UNIQUE_VIOLATION = "23505"
EXCLUSION_VIOLATION = "23P01"
RETRYABLE_VIOLATIONS = frozenset({UNIQUE_VIOLATION, EXCLUSION_VIOLATION})


def sqlstate_of(error: BaseException) -> str | None:
    """Return the SQLSTATE the driver exception carries, if it carries one."""
    # The asyncpg dialect re-wraps the driver exception in its own class, so
    # the SQLSTATE it copies over is the only thing left to recognise a
    # failure by.
    return getattr(getattr(error, "orig", None), "sqlstate", None)


@app_error
class LockTimeoutError(AppError):
    """Raised when the aggregate row stayed locked longer than the configured wait."""

    code: ClassVar[str] = "LOCK_TIMEOUT"
    message: str = "The record is busy, retry the request"
