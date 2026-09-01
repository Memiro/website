from dataclasses import replace
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

import pytest

from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.catalog.attribute.entity import Attribute, AttributeValue
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.common.identifiers import AttributeValueId
from memiro.entities.common.money import Money
from tests.common.factory.catalog import (
    BACKLIGHT,
    CUTOUT,
    GRAPHITE,
    SILVER,
    demo_blade,
    demo_cutouts,
    demo_heating,
    demo_shape,
)

_STRANGER: AttributeValueId = uuid4()


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
        scaled_by_size_surcharge=True,
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


@pytest.mark.parametrize(
    ("value_id", "quantity", "expected"),
    [
        (SILVER, None, ChosenValue(value_id=SILVER, quantity=None)),
        (GRAPHITE, None, ChosenValue(value_id=GRAPHITE, quantity=None)),
        (None, None, None),
        (None, Decimal(2), None),
        (SILVER, Decimal(2), None),
        (_STRANGER, None, None),
    ],
)
def test_a_select_attribute_configures_only_a_row_of_its_own_dictionary(
    value_id: AttributeValueId | None,
    quantity: Decimal | None,
    expected: ChosenValue | None,
) -> None:
    """A select attribute answers a form row with its value, and a stranger with nothing."""
    blade = demo_blade()

    assert blade.configure(value_id, quantity) == expected


@pytest.mark.parametrize(
    ("value_id", "quantity", "expected"),
    [
        (None, Decimal("2.5"), ChosenValue(value_id=None, quantity=Decimal("2.5"))),
        (None, Decimal(0), ChosenValue(value_id=None, quantity=Decimal(0))),
        (None, None, None),
        (CUTOUT, None, None),
        (CUTOUT, Decimal(1), None),
    ],
)
def test_a_numeric_attribute_configures_only_a_quantity(
    value_id: AttributeValueId | None,
    quantity: Decimal | None,
    expected: ChosenValue | None,
) -> None:
    """A numeric attribute answers a quantity with its value, and a dictionary row with nothing."""
    cutouts = demo_cutouts()

    assert cutouts.configure(value_id, quantity) == expected


def test_a_select_attribute_charges_a_chosen_value_by_the_row_it_names() -> None:
    """A chosen dictionary row is resolved to the row that carries its tariff."""
    blade = demo_blade()

    assert blade.row_of(ChosenValue(value_id=GRAPHITE, quantity=None)) == blade.value(GRAPHITE)


def test_a_numeric_attribute_charges_a_quantity_by_its_single_tariff_row() -> None:
    """A chosen quantity is resolved to the sole row of the numeric dictionary."""
    cutouts = demo_cutouts()

    assert cutouts.row_of(ChosenValue(value_id=None, quantity=Decimal(2))) == cutouts.values[0]


@pytest.mark.parametrize(
    "chosen",
    [
        ChosenValue(value_id=None, quantity=None),
        ChosenValue(value_id=None, quantity=Decimal(2)),
        ChosenValue(value_id=_STRANGER, quantity=None),
    ],
)
def test_a_select_attribute_charges_nothing_for_a_value_that_is_not_its_own(chosen: ChosenValue) -> None:
    """A value the attribute cannot configure has no tariff row of its own."""
    blade = demo_blade()

    assert blade.row_of(chosen) is None
