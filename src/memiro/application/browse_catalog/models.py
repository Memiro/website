from decimal import Decimal
from typing import Final
from uuid import UUID

from pydantic import BaseModel

from memiro.entities.catalog.attribute.entity import AttributeKind

# The storefront asks for whole catalogue lists; the envelope still names the
# page it answers with, so pagination can arrive without a contract change.
FIRST_PAGE: Final = 1


class CategoryModel(BaseModel):
    """One category visible on the storefront."""

    name: str
    slug: str


class CategoriesList(BaseModel):
    """One page of storefront categories."""

    items: list[CategoryModel]
    total: int
    page: int


class ProductSummary(BaseModel):
    """The compact product projection used in a category listing."""

    name: str
    slug: str
    price_from: Decimal | None
    image_keys: list[str]


class ProductsList(BaseModel):
    """One page of a category's public products."""

    items: list[ProductSummary]
    total: int
    page: int


class ProductModel(ProductSummary):
    """The full public product card projection."""

    id: UUID
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
    kind: AttributeKind
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
