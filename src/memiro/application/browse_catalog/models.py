from decimal import Decimal
from enum import StrEnum
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from memiro.entities.catalog.attribute.entity import AttributeKind

# The storefront asks for whole catalogue lists; the envelope still names the
# page it answers with, so pagination can arrive without a contract change.
FIRST_PAGE: Final = 1
PAGE_SIZE: Final = 24
MAX_FILTER_VALUES: Final = 50


class CatalogSort(StrEnum):
    """The orders a visitor may put a category listing in."""

    NAME = "name"
    CHEAPEST = "cheapest"
    DEAREST = "dearest"


class CatalogQuery(BaseModel):
    """How the visitor narrowed and ordered a category listing.

    Values of one attribute widen the answer (OR), values of different
    attributes narrow it (AND). A value that is not a filterable value of
    this category is dropped: an old link is still a page of the category.
    """

    # The query string repeats ``?value=`` per checkbox, the way a GET form
    # of the sidebar submits it.
    model_config = ConfigDict(populate_by_name=True)

    values: list[UUID] = Field(default_factory=list[UUID], max_length=MAX_FILTER_VALUES, alias="value")
    price_min: Decimal | None = Field(default=None, ge=0)
    price_max: Decimal | None = Field(default=None, ge=0)
    sort: CatalogSort = CatalogSort.NAME
    page: int = Field(default=FIRST_PAGE, ge=FIRST_PAGE)


class FilterOption(BaseModel):
    """One checkbox of a filter group: a dictionary row and how much it leaves."""

    value_id: UUID
    name: str
    count: int
    is_selected: bool


class FilterGroup(BaseModel):
    """One filterable attribute of the category with its rows."""

    attribute_id: UUID
    name: str
    options: list[FilterOption]


class PriceBounds(BaseModel):
    """The cheapest and the dearest published product of the category, and what the visitor asked for."""

    lowest: Decimal | None
    highest: Decimal | None
    selected_min: Decimal | None
    selected_max: Decimal | None


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
    """One page of a category's public products, with what narrows the rest of them."""

    items: list[ProductSummary]
    total: int
    page: int
    pages: int = FIRST_PAGE
    groups: list[FilterGroup] = Field(default_factory=list[FilterGroup])
    price: PriceBounds | None = None
    sort: CatalogSort = CatalogSort.NAME


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
    # What the product itself is made of on this attribute: the storefront
    # prints the characteristics from it and opens the calculator on it.
    # A numeric attribute declares a quantity instead, carried by its row.
    declared_value_id: UUID | None
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
