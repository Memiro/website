from typing import ClassVar

from memiro_common.errors import AppError, app_error


@app_error
class InvalidFactorRateError(AppError):
    """Raised when a ``FACTOR`` value is given a tariff that cannot multiply."""

    code: ClassVar[str] = "INVALID_FACTOR_RATE"
    message: str = "A FACTOR rate must be greater than zero"


@app_error
class InvalidAttributeParentError(AppError):
    """Raised when the dependence between attributes would leave the category or close a circle."""

    code: ClassVar[str] = "INVALID_ATTRIBUTE_PARENT"
    message: str = "An attribute can only depend on other attributes of its own category"


@app_error
class InvalidAttributeValueSetError(AppError):
    """Raised when a set of dictionary rows does not describe this attribute."""

    code: ClassVar[str] = "INVALID_ATTRIBUTE_VALUE_SET"
    message: str = "The set of values does not describe this attribute"
