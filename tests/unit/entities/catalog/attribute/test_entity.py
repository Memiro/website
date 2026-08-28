from dataclasses import replace
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

import pytest

from memiro.entities.catalog.attribute.entity import Attribute, AttributeValue
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.common.money import Money
from tests.common.factory.catalog import (
    BACKLIGHT,
    GRAPHITE,
    SILVER,
    demo_blade,
    demo_cutouts,
    demo_heating,
    demo_shape,
)


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


def test_an_absence_value_says_the_feature_is_not_present() -> None:
    """A dictionary row marked as absence does not make its feature present."""
    value = AttributeValue(
        id=uuid4(),
        name="Without a feature",
        rate=Rate(amount=Money(amount=Decimal(0)), unit=Unit.PIECE),
        scaled_by_shape=False,
        sort_order=1,
        marks_absence=True,
    )

    assert not value.is_present()


def test_an_attribute_requires_its_category() -> None:
    """An attribute cannot exist without an explicit category identity."""
    constructor = cast("Any", Attribute)

    with pytest.raises(TypeError):
        constructor(id=uuid4(), name="Feature", sort_order=1)


def test_an_attribute_exposes_its_parent_identifiers_immutably() -> None:
    """A caller receives dependent parent identifiers as an immutable tuple."""
    attribute = demo_heating()

    assert attribute.parent_ids == (BACKLIGHT,)


def test_an_attribute_does_not_share_a_mutable_parent_collection() -> None:
    """Mutating the constructor's list cannot mutate the attribute's parent identifiers."""
    parent_ids = [BACKLIGHT]
    attribute = replace(
        demo_heating(),
        # A dishonest runtime input proves constructor normalization.
        parent_ids=parent_ids,  # type: ignore[arg-type]
    )

    parent_ids.append(uuid4())

    assert attribute.parent_ids == (BACKLIGHT,)


@pytest.mark.parametrize(
    "values",
    [
        [],
        [*demo_cutouts().values, replace(demo_cutouts().values[0], id=uuid4())],
    ],
)
def test_a_numeric_attribute_rejects_any_number_of_tariff_rows_except_one(
    values: list[AttributeValue],
) -> None:
    """A numeric attribute without exactly one tariff row is a dictionary defect."""
    with pytest.raises(RuntimeError, match=r"Numeric attribute .* needs exactly one tariff row"):
        replace(demo_cutouts(), values=values)
