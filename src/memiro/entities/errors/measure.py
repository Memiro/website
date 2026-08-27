from typing import ClassVar

from memiro_common.errors import AppError, app_error


@app_error
class NegativeMeasureError(AppError):
    """Raised when a measure is given a negative value."""

    code: ClassVar[str] = "NEGATIVE_MEASURE"
    message: str = "A measure cannot be negative"


@app_error
class EmptyDimensionsError(AppError):
    """Raised when a side of the product is not strictly positive."""

    code: ClassVar[str] = "EMPTY_DIMENSIONS"
    message: str = "Both sides of the product must be positive"
