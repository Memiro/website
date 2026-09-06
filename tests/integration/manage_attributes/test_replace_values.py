from decimal import Decimal
from uuid import uuid4

import pytest
from dishka import AsyncContainer
from pydantic import ValidationError

from memiro.application.common.input_limits import MAX_ATTRIBUTE_VALUES
from memiro.application.errors.catalog import AttributeNotFoundError, AttributeValueInUseError
from memiro.application.manage_attributes import ReplaceValues, ReplaceValuesForm
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.common.identifiers import AttributeId
from memiro.entities.common.money import Money
from memiro.entities.errors.attribute import InvalidAttributeValueSetError, InvalidFactorRateError
from tests.common.factory.catalog import BACKLIGHT, CONTOUR, NO_BACKLIGHT
from tests.integration.manage_attributes.arrange import load_attribute, value_form

pytestmark = pytest.mark.usefixtures("dictionary")

# What the demo backlight holds before a command touches it: the contour tape
# and the row that says there is no backlight at all.
KEPT_CONTOUR = value_form(value_id=CONTOUR, name="Контурная")
KEPT_ABSENCE = value_form(value_id=NO_BACKLIGHT, name="Без подсветки", amount="0", sort_order=2, marks_absence=True)


async def _replace(container: AsyncContainer, attribute_id: AttributeId, form: ReplaceValuesForm) -> None:
    """Execute one dictionary replacement in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(ReplaceValues)
        await interactor.execute(attribute_id, form)


async def test_the_owner_reprices_a_row_the_products_keep(container: AsyncContainer) -> None:
    """A named row is edited in place: the identifier products declare survives the command."""
    await _replace(
        container,
        BACKLIGHT,
        ReplaceValuesForm(values=[value_form(value_id=CONTOUR, name="Контурная", amount="3000"), KEPT_ABSENCE]),
    )

    attribute = await load_attribute(container, BACKLIGHT)
    assert attribute is not None
    contour = attribute.value(CONTOUR)
    assert contour is not None
    assert contour.rate == Rate(amount=Money(amount=Decimal(3000)), unit=Unit.LINEAR_METER)


async def test_a_row_the_owner_typed_fresh_joins_the_dictionary(container: AsyncContainer) -> None:
    """A row without an identifier is stored under one of its own."""
    await _replace(
        container,
        BACKLIGHT,
        ReplaceValuesForm(values=[KEPT_CONTOUR, KEPT_ABSENCE, value_form(name="Рассеянная", sort_order=3)]),
    )

    attribute = await load_attribute(container, BACKLIGHT)
    assert attribute is not None
    assert [value.name for value in attribute.values] == ["Контурная", "Без подсветки", "Рассеянная"]


async def test_a_row_nobody_declared_leaves_the_dictionary(container: AsyncContainer) -> None:
    """The set is replaced, not merged: an unused row the owner did not name is deleted."""
    await _replace(container, BACKLIGHT, ReplaceValuesForm(values=[KEPT_ABSENCE]))

    attribute = await load_attribute(container, BACKLIGHT)
    assert attribute is not None
    assert [value.id for value in attribute.values] == [NO_BACKLIGHT]


async def test_replacing_the_values_moves_the_attribute_forward_in_time(container: AsyncContainer) -> None:
    """The command stamps ``updated_at``, and the catalogue was arranged well before it."""
    before = await load_attribute(container, BACKLIGHT)
    assert before is not None

    await _replace(container, BACKLIGHT, ReplaceValuesForm(values=[KEPT_CONTOUR, KEPT_ABSENCE]))

    after = await load_attribute(container, BACKLIGHT)
    assert after is not None
    assert after.updated_at > before.updated_at


async def test_replacing_the_values_fails_if_a_row_belongs_to_another_attribute(container: AsyncContainer) -> None:
    """INVALID_ATTRIBUTE_VALUE_SET: a set may only keep rows this attribute owns."""
    with pytest.raises(InvalidAttributeValueSetError):
        await _replace(container, BACKLIGHT, ReplaceValuesForm(values=[value_form(value_id=uuid4(), name="Чужая")]))


async def test_replacing_the_values_fails_on_a_free_multiplier(container: AsyncContainer) -> None:
    """INVALID_FACTOR_RATE: a FACTOR of zero would annihilate the price instead of scaling it."""
    with pytest.raises(InvalidFactorRateError):
        await _replace(
            container,
            BACKLIGHT,
            ReplaceValuesForm(values=[value_form(name="Никакая", amount="0", unit=Unit.FACTOR)]),
        )


async def test_replacing_the_values_fails_on_one_row_over_the_limit() -> None:
    """VALIDATION_ERROR: the form refuses more rows than the production constant allows."""
    with pytest.raises(ValidationError):
        ReplaceValuesForm(
            values=[value_form(name=f"Значение {number}") for number in range(MAX_ATTRIBUTE_VALUES + 1)],
        )


async def test_removing_a_declared_row_fails_and_names_the_products(container: AsyncContainer) -> None:
    """ATTRIBUTE_VALUE_IN_USE: the canonical mirror declares "no backlight", so that row stays."""
    with pytest.raises(AttributeValueInUseError) as refusal:
        await _replace(container, BACKLIGHT, ReplaceValuesForm(values=[KEPT_CONTOUR]))

    assert refusal.value.meta == {"products": ["Зеркало в раме"]}


async def test_a_refused_removal_leaves_the_dictionary_untouched(container: AsyncContainer) -> None:
    """A refused command deletes nothing: both rows are where the arrangement left them."""
    with pytest.raises(AttributeValueInUseError):
        await _replace(container, BACKLIGHT, ReplaceValuesForm(values=[KEPT_CONTOUR]))

    attribute = await load_attribute(container, BACKLIGHT)
    assert attribute is not None
    assert [value.id for value in attribute.values] == [CONTOUR, NO_BACKLIGHT]


async def test_replacing_the_values_fails_if_there_is_no_such_attribute(container: AsyncContainer) -> None:
    """ATTRIBUTE_NOT_FOUND: an identifier nobody issued names nothing."""
    with pytest.raises(AttributeNotFoundError):
        await _replace(container, uuid4(), ReplaceValuesForm(values=[value_form(name="Контурная")]))
