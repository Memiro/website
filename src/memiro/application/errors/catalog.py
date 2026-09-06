from typing import Any, ClassVar, override

from memiro_common.errors import AppError, app_error


@app_error
class CategoryNotFoundError(AppError):
    """Raised when the requested category does not exist."""

    code: ClassVar[str] = "CATEGORY_NOT_FOUND"
    message: str = "Category not found"


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


@app_error
class AttributeNotFoundError(AppError):
    """Raised when the requested attribute does not exist."""

    code: ClassVar[str] = "ATTRIBUTE_NOT_FOUND"
    message: str = "Attribute not found"


@app_error
class AttributeValueInUseError(AppError):
    """Raised when a dictionary row leaving the set is declared by products."""

    code: ClassVar[str] = "ATTRIBUTE_VALUE_IN_USE"
    message: str = "A dictionary value declared by products cannot be removed"
    products: tuple[str, ...] = ()

    @property
    @override
    def meta(self) -> dict[str, Any] | None:
        """Name the products the owner has to free before the row can go."""
        return {"products": list(self.products)}


@app_error
class AttributeInUseError(AppError):
    """Raised when an attribute being removed is declared by products or depended on by attributes."""

    code: ClassVar[str] = "ATTRIBUTE_IN_USE"
    message: str = "An attribute something still uses cannot be removed"
    products: tuple[str, ...] = ()
    attributes: tuple[str, ...] = ()

    @property
    @override
    def meta(self) -> dict[str, Any] | None:
        """Name everything the owner has to free before the attribute can go."""
        return {"products": list(self.products), "attributes": list(self.attributes)}


@app_error
class ProductSlugTakenError(AppError):
    """Raised when the public address of a product belongs to another product.

    Uniqueness is a fact of the transaction and not of the aggregate — one
    product cannot see the addresses of the others — so the refusal lives here
    and not in ``entities/errors/`` (§12.2).
    """

    code: ClassVar[str] = "PRODUCT_SLUG_TAKEN"
    message: str = "The product address is already taken"
