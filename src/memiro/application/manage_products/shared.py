from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from memiro.application.common.input_limits import MAX_QUANTITY, MAX_SELECTIONS, MAX_SIDE_MM, MIN_SIDE_MM
from memiro.application.errors.catalog import AttributeValueNotFoundError
from memiro.entities.catalog.attribute.entity import Attribute, AttributeKind
from memiro.entities.catalog.product.entity import ConfiguredValue, DeclaredValue, Product, VariantData
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, VariantId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.errors.product import InvalidVariantConfigurationError
from memiro.entities.pricing.pricing_service import is_product_priceable, price_product
from memiro.entities.pricing.pricing_settings import PricingSettings


def _overrides(
    product: Product,
    attributes: Sequence[Attribute],
    forms: Sequence[VariantOverrideForm],
) -> tuple[DeclaredValue, ...]:
    """Resolve only values belonging to the product category and their named attribute."""
    index = {attribute.id: attribute for attribute in attributes if attribute.category_id == product.category_id}
    resolved: list[DeclaredValue] = []
    for form in forms:
        attribute_id: AttributeId = form.attribute_id
        attribute = index.get(attribute_id)
        configured: ConfiguredValue | None = None
        if attribute is not None:
            value_id: AttributeValueId | None = form.value_id
            if (
                attribute.kind is AttributeKind.SELECT
                and value_id is not None
                and attribute.value(value_id) is not None
            ):
                configured = ConfiguredValue(value_id=value_id, quantity=None)
            elif attribute.kind is AttributeKind.NUMBER and form.quantity is not None:
                configured = ConfiguredValue(value_id=None, quantity=form.quantity)
        if configured is None:
            raise AttributeValueNotFoundError
        resolved.append(DeclaredValue(attribute_id=attribute_id, configured=configured))
    return tuple(resolved)


class VariantOverrideForm(BaseModel):
    """One dictionary value or numeric quantity replacing the product's declaration."""

    attribute_id: AttributeId
    value_id: AttributeValueId | None = None
    quantity: Decimal | None = Field(default=None, ge=0, le=MAX_QUANTITY)

    @model_validator(mode="after")
    def _one_representation(self) -> VariantOverrideForm:
        """Require exactly one representation of the override."""
        if (self.value_id is None) is (self.quantity is None):
            msg = "A variant override must name exactly one of value_id and quantity"
            raise ValueError(msg)
        return self


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


def variant_price(
    data: VariantData,
    *,
    product: Product,
    attributes: Sequence[Attribute],
    settings: PricingSettings,
) -> Money:
    """Price a variant through the owner path of the single pricing service."""
    selections = {override.attribute_id: override.configured for override in data.overrides}
    if not is_product_priceable(product, attributes, selections):
        raise InvalidVariantConfigurationError(
            message="A variant configuration must contain every applicable paid value",
        )
    quotation = price_product(
        product=product,
        attributes=attributes,
        settings=settings,
        dimensions=data.dimensions,
        selections=selections,
    )
    if quotation.total is None:
        msg = "The owner pricing path returned a quotation without a total"
        raise RuntimeError(msg)
    return quotation.total
