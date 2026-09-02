from decimal import Decimal
from uuid import uuid4

import pytest

from memiro.entities.catalog.attribute.entity import Attribute, AttributeValueData
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.common.identifiers import AttributeValueId
from memiro.entities.common.money import Money
from memiro.entities.errors.attribute import InvalidAttributeValueSetError
from tests.clock import CLOCK, LATER, LATER_CLOCK
from tests.common.factory.catalog import CONTOUR, NO_BACKLIGHT, demo_backlight, demo_cutouts

_STRANGER: AttributeValueId = uuid4()


def _row(
    value_id: AttributeValueId | None,
    *,
    name: str,
    amount: str = "2500",
    sort_order: int = 1,
    marks_absence: bool = False,
) -> AttributeValueData:
    """Build one row of the replacement set as the owner's form carries it."""
    return AttributeValueData(
        id=value_id,
        name=name,
        rate=Rate(amount=Money(amount=Decimal(amount)), unit=Unit.LINEAR_METER),
        scaled_by_shape=False,
        scaled_by_size_surcharge=False,
        marks_absence=marks_absence,
        sort_order=sort_order,
    )


def test_the_owner_reprices_a_row_the_products_keep() -> None:
    """A named row is edited in place: the identifier products declare survives."""
    backlight = demo_backlight()

    backlight.replace_values(
        [
            _row(CONTOUR, name="Контурная", amount="3000"),
            _row(NO_BACKLIGHT, name="Без подсветки", amount="0", sort_order=2, marks_absence=True),
        ],
        clock=LATER_CLOCK,
    )

    contour = backlight.value(CONTOUR)
    assert contour is not None
    assert contour.rate == Rate(amount=Money(amount=Decimal(3000)), unit=Unit.LINEAR_METER)


def test_a_replacement_set_drops_every_row_it_does_not_name() -> None:
    """The set is replaced, not merged: an unnamed row leaves the dictionary."""
    backlight = demo_backlight()

    backlight.replace_values([_row(CONTOUR, name="Контурная")], clock=LATER_CLOCK)

    assert [value.id for value in backlight.values] == [CONTOUR]


def test_a_row_without_an_identifier_joins_the_dictionary() -> None:
    """A row the owner typed fresh is created with an identifier of its own."""
    backlight = demo_backlight()

    backlight.replace_values(
        [_row(CONTOUR, name="Контурная"), _row(None, name="Рассеянная", sort_order=3)],
        clock=LATER_CLOCK,
    )

    added = next(value for value in backlight.values if value.name == "Рассеянная")
    assert added.id not in {CONTOUR, NO_BACKLIGHT}


def test_replacing_the_values_moves_the_attribute_forward_in_time() -> None:
    """The command stamps ``updated_at`` from the clock it is given."""
    backlight = demo_backlight()

    backlight.replace_values([_row(CONTOUR, name="Контурная")], clock=LATER_CLOCK)

    assert backlight.updated_at == LATER


def test_a_replacement_set_fails_if_it_names_a_row_of_another_attribute() -> None:
    """INVALID_ATTRIBUTE_VALUE_SET: a set may only keep rows this attribute owns."""
    backlight = demo_backlight()

    with pytest.raises(InvalidAttributeValueSetError):
        backlight.replace_values([_row(_STRANGER, name="Чужая")], clock=LATER_CLOCK)


def test_a_replacement_set_fails_if_it_names_one_row_twice() -> None:
    """INVALID_ATTRIBUTE_VALUE_SET: one dictionary row cannot be two rows of the set."""
    backlight = demo_backlight()

    with pytest.raises(InvalidAttributeValueSetError):
        backlight.replace_values(
            [_row(CONTOUR, name="Контурная"), _row(CONTOUR, name="Контурная снова", sort_order=2)],
            clock=LATER_CLOCK,
        )


def test_a_numeric_attribute_fails_if_its_set_does_not_hold_exactly_one_row() -> None:
    """INVALID_ATTRIBUTE_VALUE_SET: a numeric attribute charges by exactly one tariff."""
    cutouts = demo_cutouts()

    with pytest.raises(InvalidAttributeValueSetError):
        cutouts.replace_values([], clock=LATER_CLOCK)


def test_an_attribute_tells_which_rows_a_replacement_would_remove() -> None:
    """The aggregate names the rows leaving the dictionary, so the caller can check their use."""
    backlight = demo_backlight()

    absent = backlight.values_absent_from([_row(CONTOUR, name="Контурная")])

    assert absent == (NO_BACKLIGHT,)


def test_a_refused_replacement_leaves_the_dictionary_untouched() -> None:
    """A rejected set changes neither the rows nor the moment the attribute last moved."""
    backlight = demo_backlight()
    before = [value.name for value in backlight.values]

    with pytest.raises(InvalidAttributeValueSetError):
        backlight.replace_values([_row(_STRANGER, name="Чужая")], clock=LATER_CLOCK)

    assert [value.name for value in backlight.values] == before
    assert backlight.updated_at == demo_backlight().updated_at


def test_an_attribute_born_and_replaced_keeps_the_moment_it_was_born_at() -> None:
    """``created_at`` is not touched by a command that only replaces the dictionary."""
    backlight: Attribute = demo_backlight()
    born_at = backlight.created_at

    backlight.replace_values([_row(CONTOUR, name="Контурная")], clock=CLOCK)

    assert backlight.created_at == born_at
