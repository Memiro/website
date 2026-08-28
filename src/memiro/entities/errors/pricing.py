from typing import ClassVar

from memiro_common.errors import AppError, app_error


@app_error
class InvalidSurchargeFactorError(AppError):
    """Raised when a size-surcharge tier would not raise the price."""

    code: ClassVar[str] = "INVALID_SURCHARGE_FACTOR"
    message: str = "A size-surcharge factor must be greater than one"


@app_error
class DuplicateSizeSurchargeError(AppError):
    """Raised when two size-surcharge tiers start at the same threshold."""

    code: ClassVar[str] = "DUPLICATE_SIZE_SURCHARGE"
    message: str = "Size-surcharge thresholds must be unique"
