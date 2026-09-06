from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

import structlog
from pydantic import BaseModel, Field, model_validator

from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.input_limits import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MAX_QUANTITY,
    MAX_SELECTIONS,
    MAX_SIDE_MM,
    MIN_NAME_LENGTH,
    MIN_SIDE_MM,
)
from memiro.application.errors.catalog import (
    AttributeValueNotFoundError,
    ProductNotFoundError,
    ProductSlugTakenError,
)
from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.catalog.product.entity import (
    ChangeProductData,
    CreateProductData,
    DeclaredValue,
    Product,
    VariantData,
)
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, CategoryId, ProductId, VariantId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)

# Either the address the owner typed — lowercase latin words joined by single
# hyphens — or nothing, which the domain fills in from the name. The form
# refuses anything else instead of quietly rewriting what the owner entered.
SLUG_PATTERN = r"^$|^[a-z0-9]+(?:-[a-z0-9]+)*$"


def _overrides(
    product: Product,
    attributes: Sequence[Attribute],
    forms: Sequence[VariantOverrideForm],
) -> tuple[DeclaredValue, ...]:
    """Resolve only values the product declares, belonging to its category and their named attribute.

    A variant replaces what the product declared, it does not introduce a
    setting the product never had — the same rule the customer's choice obeys
    (ADR-0007).
    """
    for form in forms:
        if product.declared(form.attribute_id) is None:
            raise AttributeValueNotFoundError
    return as_declarations(product, attributes, forms)


class ChosenValueForm(BaseModel):
    """One dictionary value or numeric quantity the owner set on one attribute."""

    attribute_id: AttributeId
    value_id: AttributeValueId | None = None
    quantity: Decimal | None = Field(default=None, ge=0, le=MAX_QUANTITY)

    @model_validator(mode="after")
    def _one_representation(self) -> ChosenValueForm:
        """Require exactly one representation of the chosen value."""
        if (self.value_id is None) is (self.quantity is None):
            msg = "A chosen value must name exactly one of value_id and quantity"
            raise ValueError(msg)
        return self


class VariantOverrideForm(ChosenValueForm):
    """One chosen value replacing what the product declared on that attribute."""


class VariantForm(BaseModel):
    """Owner-controlled fields shared by adding and changing a variant."""

    width_mm: int = Field(ge=MIN_SIDE_MM, le=MAX_SIDE_MM)
    height_mm: int = Field(ge=MIN_SIDE_MM, le=MAX_SIDE_MM)
    overrides: list[VariantOverrideForm] = Field(
        default_factory=list[VariantOverrideForm],
        max_length=MAX_SELECTIONS,
    )
    sort_order: int = 0

    @model_validator(mode="after")
    def _one_override_per_attribute(self) -> VariantForm:
        """Refuse two overrides that would compete for one product declaration."""
        attribute_ids = [override.attribute_id for override in self.overrides]
        if len(set(attribute_ids)) != len(attribute_ids):
            msg = "A variant can override an attribute only once"
            raise ValueError(msg)
        return self


class CreatedVariant(BaseModel):
    """Identifier of a newly created product variant."""

    id: VariantId


def variant_data(
    form: VariantForm,
    *,
    product: Product,
    attributes: Sequence[Attribute],
) -> VariantData:
    """Resolve an owner's form into the aggregate's command data."""
    return VariantData(
        dimensions=Dimensions(
            width=Millimeters(value=form.width_mm),
            height=Millimeters(value=form.height_mm),
        ),
        overrides=_overrides(product, attributes, form.overrides),
        sort_order=form.sort_order,
    )


class ProductForm(BaseModel):
    """Owner-controlled root fields shared by creating and changing a product."""

    category_id: CategoryId
    name: str = Field(min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH)
    slug: str = Field(default="", max_length=MAX_NAME_LENGTH, pattern=SLUG_PATTERN)
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LENGTH)
    is_published: bool = False
    hides_calculated_price: bool = False


def create_data(form: ProductForm) -> CreateProductData:
    """Resolve the owner's card into the data the product is created from."""
    return CreateProductData(
        category_id=form.category_id,
        name=form.name,
        slug=form.slug,
        description=form.description,
        is_published=form.is_published,
        hides_calculated_price=form.hides_calculated_price,
    )


def change_data(form: ProductForm) -> ChangeProductData:
    """Resolve the owner's card into the data the product is restated by."""
    return ChangeProductData(
        category_id=form.category_id,
        name=form.name,
        slug=form.slug,
        description=form.description,
        is_published=form.is_published,
        hides_calculated_price=form.hides_calculated_price,
    )


async def loaded_for_update(gateway: ProductGateway, product_id: ProductId, *, command: str) -> Product:
    """Load one product under its lock, with its children, refusing an identifier nobody issued."""
    product = await gateway.get(product_id, for_update=True, eager_variants=True)
    if product is None:
        logger.warning("A command named an unknown product", product_id=product_id, command=command)
        raise ProductNotFoundError
    return product


async def ensure_the_address_is_free(
    gateway: ProductGateway,
    slug: str,
    *,
    except_product: ProductId | None,
) -> None:
    """Refuse an address another product already answers on."""
    holder = await gateway.slug_owner(slug)
    if holder is not None and holder != except_product:
        logger.warning("A product address is already taken", slug=slug)
        raise ProductSlugTakenError


class DeclarationForm(ChosenValueForm):
    """One chosen value the owner declares for the product on an attribute of its section."""


def as_declarations(
    product: Product,
    attributes: Sequence[Attribute],
    forms: Sequence[ChosenValueForm],
) -> tuple[DeclaredValue, ...]:
    """Resolve the owner's set into declarations on the attributes of the product's own section."""
    index = {attribute.id: attribute for attribute in attributes if attribute.category_id == product.category_id}
    resolved: list[DeclaredValue] = []
    for form in forms:
        attribute = index.get(form.attribute_id)
        chosen = attribute.configure(form.value_id, form.quantity) if attribute is not None else None
        if chosen is None:
            raise AttributeValueNotFoundError
        resolved.append(DeclaredValue(attribute_id=form.attribute_id, chosen=chosen))
    return tuple(resolved)
