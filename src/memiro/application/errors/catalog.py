from typing import ClassVar

from memiro_common.errors import AppError, app_error


@app_error
class ProductNotFoundError(AppError):
    """Raised when the requested product does not exist."""

    code: ClassVar[str] = "PRODUCT_NOT_FOUND"
    message: str = "Product not found"


@app_error
class VariantNotFoundError(AppError):
    """Raised when a requested child does not belong to the product."""

    code: ClassVar[str] = "VARIANT_NOT_FOUND"
    message: str = "Variant not found"


@app_error
class AttributeValueNotFoundError(AppError):
    """Raised when a chosen dictionary value cannot be used for this product.

    One code for three shapes of the same miss — the value does not exist, it
    belongs to another attribute, or the product declares nothing on that
    attribute — because the customer's answer is the same: this choice is not
    on offer. A finer code would tell an outsider what the catalogue holds.
    """

    code: ClassVar[str] = "ATTRIBUTE_VALUE_NOT_FOUND"
    message: str = "Attribute value not found"
