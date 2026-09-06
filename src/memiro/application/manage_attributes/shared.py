from decimal import Decimal

import structlog
from pydantic import BaseModel, Field

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.input_limits import (
    MAX_ATTRIBUTE_PARENTS,
    MAX_ATTRIBUTE_VALUES,
    MAX_NAME_LENGTH,
    MAX_RATE_AMOUNT,
    MIN_NAME_LENGTH,
)
from memiro.application.errors.catalog import AttributeNotFoundError
from memiro.entities.catalog.attribute.entity import (
    Attribute,
    AttributeKind,
    AttributeValueData,
    ReplacementValueData,
)
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.common.identifiers import AttributeId, AttributeValueId
from memiro.entities.common.money import Money
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)


class AttributeValueForm(BaseModel):
    """One row of the dictionary as the owner's card submits it."""

    name: str = Field(min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH)
    rate_amount: Decimal = Field(ge=0, le=MAX_RATE_AMOUNT)
    rate_unit: Unit
    scaled_by_shape: bool = False
    scaled_by_size_surcharge: bool = False
    marks_absence: bool = False
    sort_order: int = Field(default=0, ge=0)


class ReplacementValueForm(AttributeValueForm):
    """One row of a replacement set: the same fields, plus the row it keeps."""

    id: AttributeValueId | None = None


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

    values: list[ReplacementValueForm] = Field(
        default_factory=list[ReplacementValueForm],
        max_length=MAX_ATTRIBUTE_VALUES,
    )


def as_value_data(form: AttributeValueForm) -> AttributeValueData:
    """Resolve one of the owner's rows into the aggregate's command data."""
    return AttributeValueData(
        name=form.name,
        rate=Rate(amount=Money(amount=form.rate_amount), unit=form.rate_unit),
        scaled_by_shape=form.scaled_by_shape,
        scaled_by_size_surcharge=form.scaled_by_size_surcharge,
        marks_absence=form.marks_absence,
        sort_order=form.sort_order,
    )


def as_replacements(forms: list[ReplacementValueForm]) -> tuple[ReplacementValueData, ...]:
    """Resolve the owner's set into the rows the aggregate keeps and the rows it is given."""
    return tuple(ReplacementValueData(id=form.id, data=as_value_data(form)) for form in forms)


async def loaded_for_update(gateway: AttributeGateway, attribute_id: AttributeId, *, command: str) -> Attribute:
    """Load one attribute under its lock, refusing an identifier nobody issued."""
    attribute = await gateway.get(attribute_id, for_update=True)
    if attribute is None:
        logger.warning("A command named an unknown attribute", attribute_id=attribute_id, command=command)
        raise AttributeNotFoundError
    return attribute
