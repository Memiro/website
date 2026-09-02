from decimal import Decimal

from pydantic import BaseModel, Field

from memiro.application.common.input_limits import (
    MAX_ATTRIBUTE_PARENTS,
    MAX_ATTRIBUTE_VALUES,
    MAX_NAME_LENGTH,
    MAX_RATE_AMOUNT,
    MIN_NAME_LENGTH,
)
from memiro.entities.catalog.attribute.entity import AttributeKind, AttributeValueData
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.common.identifiers import AttributeId, AttributeValueId
from memiro.entities.common.money import Money


class AttributeValueForm(BaseModel):
    """One row of the dictionary as the owner's card submits it."""

    id: AttributeValueId | None = None
    name: str = Field(min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH)
    rate_amount: Decimal = Field(ge=0, le=MAX_RATE_AMOUNT)
    rate_unit: Unit
    scaled_by_shape: bool = False
    scaled_by_size_surcharge: bool = False
    marks_absence: bool = False
    sort_order: int = Field(default=0, ge=0)


class AttributeRootForm(BaseModel):
    """Owner-controlled root fields shared by creating and changing an attribute."""

    name: str = Field(min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH)
    kind: AttributeKind = AttributeKind.SELECT
    parent_ids: list[AttributeId] = Field(
        default_factory=list[AttributeId],
        max_length=MAX_ATTRIBUTE_PARENTS,
    )
    is_customer_changeable: bool = True
    is_filterable: bool = False
    sort_order: int = Field(default=0, ge=0)


class ValueSetForm(BaseModel):
    """The whole dictionary of one attribute, as the owner wants it to end up."""

    values: list[AttributeValueForm] = Field(
        default_factory=list[AttributeValueForm],
        max_length=MAX_ATTRIBUTE_VALUES,
    )


def value_data(forms: list[AttributeValueForm]) -> tuple[AttributeValueData, ...]:
    """Resolve the owner's rows into the aggregate's command data."""
    return tuple(
        AttributeValueData(
            id=form.id,
            name=form.name,
            rate=Rate(amount=Money(amount=form.rate_amount), unit=form.rate_unit),
            scaled_by_shape=form.scaled_by_shape,
            scaled_by_size_surcharge=form.scaled_by_size_surcharge,
            marks_absence=form.marks_absence,
            sort_order=form.sort_order,
        )
        for form in forms
    )
