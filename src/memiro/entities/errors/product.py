from typing import ClassVar

from memiro_common.errors import AppError, app_error


@app_error
class DuplicateVariantError(AppError):
    """Raised when a product already has the same size and effective values."""

    code: ClassVar[str] = "DUPLICATE_VARIANT"
    message: str = "A product cannot have two variants with the same size and configured values"


@app_error
class InvalidVariantSortOrderError(AppError):
    """Raised when a variant would have a negative owner order."""

    code: ClassVar[str] = "INVALID_VARIANT_SORT_ORDER"
    message: str = "A variant sort order cannot be negative"


@app_error
class InvalidVariantConfigurationError(AppError):
    """Raised when a variant does not describe one calculable configuration."""

    code: ClassVar[str] = "INVALID_VARIANT_CONFIGURATION"
    message: str = "A variant configuration is invalid"
