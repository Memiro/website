import pytest

from memiro.entities.catalog.attribute.entity import AttributeKind, ChangeAttributeData
from memiro.entities.errors.attribute import InvalidAttributeValueSetError
from tests.clock import LATER, LATER_CLOCK
from tests.common.factory.catalog import BACKLIGHT, demo_backlight, demo_cutouts

# Where the owner moves the attribute to in the card.
PLACE_IN_THE_CARD = 9


def _data(  # noqa: PLR0913  # one keyword per root field of the attribute the owner fills in
    *,
    name: str = "Подсветка зеркала",
    kind: AttributeKind = AttributeKind.SELECT,
    parent_ids: tuple[object, ...] = (),
    is_customer_changeable: bool = False,
    is_filterable: bool = True,
    sort_order: int = PLACE_IN_THE_CARD,
) -> ChangeAttributeData:
    """Build the owner's form for the root of an attribute."""
    return ChangeAttributeData(
        name=name,
        kind=kind,
        parent_ids=parent_ids,  # type: ignore[arg-type]  # identifiers are plain UUIDs
        is_customer_changeable=is_customer_changeable,
        is_filterable=is_filterable,
        sort_order=sort_order,
    )


def test_the_owner_restates_the_root_of_an_attribute() -> None:
    """Every root field the owner typed replaces the one the attribute had."""
    backlight = demo_backlight()

    backlight.change(_data(parent_ids=(BACKLIGHT,)), clock=LATER_CLOCK)

    assert backlight.name == "Подсветка зеркала"
    assert backlight.kind is AttributeKind.SELECT
    assert backlight.parent_ids == (BACKLIGHT,)
    assert backlight.is_customer_changeable is False
    assert backlight.is_filterable is True
    assert backlight.sort_order == PLACE_IN_THE_CARD
    assert backlight.updated_at == LATER


def test_changing_the_root_leaves_the_dictionary_where_it_was() -> None:
    """The root command is not a dictionary command: the rows stay as they are."""
    backlight = demo_backlight()
    before = [value.id for value in backlight.values]

    backlight.change(_data(), clock=LATER_CLOCK)

    assert [value.id for value in backlight.values] == before


def test_an_attribute_fails_if_it_turns_numeric_with_a_dictionary_of_two() -> None:
    """INVALID_ATTRIBUTE_VALUE_SET: a numeric attribute charges by exactly one tariff."""
    backlight = demo_backlight()

    with pytest.raises(InvalidAttributeValueSetError, match="exactly one tariff row"):
        backlight.change(_data(kind=AttributeKind.NUMBER), clock=LATER_CLOCK)


def test_an_attribute_with_one_row_may_turn_numeric() -> None:
    """A dictionary already holding one row satisfies the shape a numeric attribute needs."""
    cutouts = demo_cutouts()

    cutouts.change(_data(name="Вырезы", kind=AttributeKind.NUMBER), clock=LATER_CLOCK)

    assert cutouts.kind is AttributeKind.NUMBER


def test_a_refused_root_change_leaves_the_attribute_untouched() -> None:
    """A rejected form changes neither the name nor the moment the attribute last moved."""
    backlight = demo_backlight()

    with pytest.raises(InvalidAttributeValueSetError, match="exactly one tariff row"):
        backlight.change(_data(kind=AttributeKind.NUMBER), clock=LATER_CLOCK)

    assert backlight.name == demo_backlight().name
    assert backlight.updated_at == demo_backlight().updated_at
