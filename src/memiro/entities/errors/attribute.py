from typing import ClassVar

from memiro_common.errors import AppError, app_error


@app_error
class InvalidFactorRateError(AppError):
    """Raised when a ``FACTOR`` value is given a tariff that cannot multiply."""

    code: ClassVar[str] = "INVALID_FACTOR_RATE"
    message: str = "A FACTOR rate must be greater than zero"
