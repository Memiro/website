from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class CategoryModel(BaseModel):
    """One category visible on the storefront."""

    name: str
    slug: str


class ProductSummary(BaseModel):
    """The compact product projection used in a category listing."""

    name: str
    slug: str
    price_from: Decimal | None
    image_keys: list[str]


class ProductModel(ProductSummary):
    """The full public product card projection."""

    description: str
    attributes: list["ProductAttribute"]
    variants: list["ProductVariant"]


class ProductVariant(BaseModel):
    """One owner-ordered precalculated configuration."""

    width_mm: int
    height_mm: int
    price: Decimal
    overrides: list["VariantOverride"]


class ProductAttribute(BaseModel):
    """One declared public attribute."""

    id: UUID
    name: str
    values: list["ProductAttributeValue"]


class ProductAttributeValue(BaseModel):
    """One public dictionary value without pricing internals."""

    id: UUID | None
    name: str
    quantity: Decimal | None


class VariantOverride(BaseModel):
    """One public variant override without pricing internals."""

    attribute_id: UUID
    value_id: UUID | None
    quantity: Decimal | None
