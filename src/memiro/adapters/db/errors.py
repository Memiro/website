from typing import ClassVar

from memiro_common.errors import AppError, app_error


@app_error
class LockTimeoutError(AppError):
    """Raised when the aggregate row stayed locked longer than the configured wait."""

    code: ClassVar[str] = "LOCK_TIMEOUT"
    message: str = "The record is busy, retry the request"
