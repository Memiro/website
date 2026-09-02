"""Forms and readings the four attribute scenarios share."""

from collections.abc import Sequence
from decimal import Decimal

from dishka import AsyncContainer

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.manage_attributes import AttributeValueForm
from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.catalog.attribute.rate import Unit
from memiro.entities.common.identifiers import AttributeId, AttributeValueId


def value_form(  # noqa: PLR0913  # one keyword per column of the dictionary row the owner fills in
    *,
    value_id: AttributeValueId | None = None,
    name: str = "Контурная",
    amount: str = "2500",
    unit: Unit = Unit.LINEAR_METER,
    sort_order: int = 1,
    marks_absence: bool = False,
) -> AttributeValueForm:
    """Build one row of the dictionary as the owner's card submits it."""
    return AttributeValueForm(
        id=value_id,
        name=name,
        rate_amount=Decimal(amount),
        rate_unit=unit,
        scaled_by_shape=False,
        scaled_by_size_surcharge=False,
        marks_absence=marks_absence,
        sort_order=sort_order,
    )


async def load_dictionary(container: AsyncContainer) -> Sequence[Attribute]:
    """Read the whole dictionary back in a fresh transaction after a command."""
    async with container() as request:
        gateway: AttributeGateway = await request.get(AttributeGateway)
        return await gateway.list_with_values()


async def load_attribute(container: AsyncContainer, attribute_id: AttributeId) -> Attribute | None:
    """Read one attribute back in a fresh transaction after a command."""
    async with container() as request:
        gateway: AttributeGateway = await request.get(AttributeGateway)
        return await gateway.get(attribute_id)
