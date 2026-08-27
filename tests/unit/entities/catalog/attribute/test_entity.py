from decimal import Decimal
from uuid import uuid4

from memiro.entities.catalog.attribute.entity import AttributeValue
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.common.money import Money
from tests.common.factory.catalog import GRAPHITE, SILVER, demo_blade, demo_shape


def test_an_attribute_finds_a_row_of_its_own_dictionary() -> None:
    """An attribute answers with the whole row its identifier names."""
    blade = demo_blade()

    value = blade.value(GRAPHITE)

    # The graphite row as the demo dictionary declares it — the second place
    # to fix is tests/common/factory/catalog.py.
    assert value == AttributeValue(
        id=GRAPHITE,
        name="Графит",
        rate=Rate(amount=Money(amount=Decimal(7000)), unit=Unit.SQUARE_METER),
        scaled_by_shape=True,
        sort_order=2,
    )


def test_an_attribute_does_not_claim_a_row_nobody_issued() -> None:
    """An identifier outside the dictionary is answered with nothing, not with a guess."""
    blade = demo_blade()

    assert blade.value(uuid4()) is None


def test_an_attribute_does_not_claim_the_row_of_another_attribute() -> None:
    """The silver blade is not a row of the shape attribute, and the shape says so."""
    shape = demo_shape()

    assert shape.value(SILVER) is None
