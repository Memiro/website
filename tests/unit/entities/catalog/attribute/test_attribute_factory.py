from decimal import Decimal

import pytest

from memiro.entities.catalog.attribute.entity import (
    AttributeKind,
    AttributeValueData,
    CreateAttributeData,
    attribute_factory,
)
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.common.money import Money
from memiro.entities.errors.attribute import InvalidAttributeValueSetError
from tests.clock import CLOCK, NOW
from tests.common.factory.catalog import BACKLIGHT, CATEGORY

# Where the owner puts the new attribute in the card.
PLACE_IN_THE_CARD = 4


def _value(*, name: str = "Контурная", sort_order: int = 1) -> AttributeValueData:
    """Build one dictionary row the owner typed into the card."""
    return AttributeValueData(
        name=name,
        rate=Rate(amount=Money(amount=Decimal(2500)), unit=Unit.LINEAR_METER),
        scaled_by_shape=False,
        scaled_by_size_surcharge=False,
        marks_absence=False,
        sort_order=sort_order,
    )


def _data(*, kind: AttributeKind = AttributeKind.SELECT, values: tuple[AttributeValueData, ...]) -> CreateAttributeData:
    """Build the owner's form for a new attribute of the demo category."""
    return CreateAttributeData(
        category_id=CATEGORY,
        name="Подсветка",
        kind=kind,
        parent_ids=(BACKLIGHT,),
        is_customer_changeable=True,
        is_filterable=True,
        sort_order=PLACE_IN_THE_CARD,
        values=values,
    )


def test_a_new_attribute_is_born_with_its_dictionary() -> None:
    """A created attribute keeps every field the owner typed and the rows he listed."""
    data = _data(values=(_value(),))

    attribute = attribute_factory(data, clock=CLOCK)

    assert attribute.category_id == CATEGORY
    assert attribute.name == "Подсветка"
    assert attribute.kind is AttributeKind.SELECT
    assert attribute.parent_ids == (BACKLIGHT,)
    assert attribute.is_customer_changeable is True
    assert attribute.is_filterable is True
    assert attribute.sort_order == PLACE_IN_THE_CARD
    assert [value.name for value in attribute.values] == ["Контурная"]


def test_a_new_attribute_takes_both_of_its_dates_from_one_reading_of_the_clock() -> None:
    """Creation stamps ``created_at`` and ``updated_at`` with the same instant."""
    attribute = attribute_factory(_data(values=(_value(),)), clock=CLOCK)

    assert attribute.created_at == NOW
    assert attribute.updated_at == NOW


def test_a_new_attribute_gets_an_identifier_nobody_could_forge() -> None:
    """Two attributes created from one form are still two different attributes."""
    data = _data(values=(_value(),))

    first = attribute_factory(data, clock=CLOCK)
    second = attribute_factory(data, clock=CLOCK)

    assert first.id != second.id
    assert first.values[0].id != second.values[0].id


def test_a_new_numeric_attribute_fails_if_it_is_given_two_tariff_rows() -> None:
    """INVALID_ATTRIBUTE_VALUE_SET: a numeric attribute charges by exactly one tariff."""
    data = _data(
        kind=AttributeKind.NUMBER,
        values=(_value(name="Вырез", sort_order=1), _value(name="Второй вырез", sort_order=2)),
    )

    with pytest.raises(InvalidAttributeValueSetError, match="exactly one tariff row"):
        attribute_factory(data, clock=CLOCK)
