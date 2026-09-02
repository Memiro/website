from uuid import uuid4

import pytest
from dishka import AsyncContainer
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.common.input_limits import MAX_NAME_LENGTH
from memiro.application.errors.catalog import AttributeNotFoundError
from memiro.application.manage_attributes import ChangeAttribute, ChangeAttributeForm
from memiro.entities.catalog.attribute.entity import AttributeKind
from memiro.entities.common.identifiers import AttributeId
from memiro.entities.errors.attribute import InvalidAttributeParentError, InvalidAttributeValueSetError
from tests.common.factory.catalog import BACKLIGHT, BLADE, HEATING, MOUNT
from tests.integration.manage_attributes.arrange import load_attribute
from tests.integration.prime import prime_one_row_attribute

pytestmark = pytest.mark.usefixtures("dictionary")

# Where the owner moves the attribute to in the card.
PLACE_IN_THE_CARD = 11


def _form(**overrides: object) -> ChangeAttributeForm:
    """Build the owner's form for the root of an attribute."""
    fields: dict[str, object] = {
        "name": "Подсветка зеркала",
        "kind": AttributeKind.SELECT,
        "parent_ids": [],
        "is_customer_changeable": False,
        "is_filterable": True,
        "sort_order": PLACE_IN_THE_CARD,
    }
    return ChangeAttributeForm.model_validate(fields | overrides)


async def _change(container: AsyncContainer, attribute_id: AttributeId, form: ChangeAttributeForm) -> None:
    """Execute one root change in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(ChangeAttribute)
        await interactor.execute(attribute_id, form)


async def test_the_owner_restates_the_root_of_an_attribute(container: AsyncContainer) -> None:
    """Every root field the owner typed is what the dictionary holds afterwards."""
    await _change(container, BACKLIGHT, _form(parent_ids=[BLADE]))

    attribute = await load_attribute(container, BACKLIGHT)
    assert attribute is not None
    assert attribute.name == "Подсветка зеркала"
    assert attribute.parent_ids == (BLADE,)
    assert attribute.is_customer_changeable is False
    assert attribute.is_filterable is True
    assert attribute.sort_order == PLACE_IN_THE_CARD


async def test_changing_the_root_leaves_the_dictionary_where_it_was(container: AsyncContainer) -> None:
    """The root command is not a dictionary command: the rows stay as they are."""
    before = await load_attribute(container, BACKLIGHT)
    assert before is not None
    rows = [(value.id, value.name) for value in before.values]

    await _change(container, BACKLIGHT, _form())

    after = await load_attribute(container, BACKLIGHT)
    assert after is not None
    assert [(value.id, value.name) for value in after.values] == rows


async def test_changing_an_attribute_moves_it_forward_in_time(container: AsyncContainer) -> None:
    """The command stamps ``updated_at``, and the catalogue was arranged well before it."""
    before = await load_attribute(container, BACKLIGHT)
    assert before is not None

    await _change(container, BACKLIGHT, _form())

    after = await load_attribute(container, BACKLIGHT)
    assert after is not None
    assert after.updated_at > before.updated_at


async def test_changing_an_attribute_fails_if_there_is_no_such_attribute(container: AsyncContainer) -> None:
    """ATTRIBUTE_NOT_FOUND: an identifier nobody issued names nothing."""
    with pytest.raises(AttributeNotFoundError):
        await _change(container, uuid4(), _form())


async def test_changing_an_attribute_fails_if_it_becomes_its_own_parent(container: AsyncContainer) -> None:
    """INVALID_ATTRIBUTE_PARENT: an attribute cannot depend on itself."""
    with pytest.raises(InvalidAttributeParentError):
        await _change(container, BACKLIGHT, _form(parent_ids=[BACKLIGHT]))


async def test_changing_an_attribute_fails_if_the_parentage_closes_a_circle(container: AsyncContainer) -> None:
    """INVALID_ATTRIBUTE_PARENT: heating already depends on backlight, so backlight cannot depend on heating."""
    with pytest.raises(InvalidAttributeParentError):
        await _change(container, BACKLIGHT, _form(parent_ids=[HEATING]))


async def test_turning_an_attribute_numeric_fails_with_a_dictionary_of_two(container: AsyncContainer) -> None:
    """INVALID_ATTRIBUTE_VALUE_SET: a numeric attribute charges by exactly one tariff."""
    with pytest.raises(InvalidAttributeValueSetError):
        await _change(container, BACKLIGHT, _form(kind=AttributeKind.NUMBER))


async def test_an_attribute_with_one_row_may_turn_numeric(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """A dictionary already holding one row satisfies the shape a numeric attribute needs."""
    await prime_one_row_attribute(engine)

    await _change(container, MOUNT, _form(name="Крепления", kind=AttributeKind.NUMBER))

    attribute = await load_attribute(container, MOUNT)
    assert attribute is not None
    assert attribute.kind is AttributeKind.NUMBER


async def test_changing_an_attribute_fails_on_a_name_one_character_over_the_limit() -> None:
    """VALIDATION_ERROR: the form refuses a name longer than the production constant allows."""
    with pytest.raises(ValidationError):
        _form(name="я" * (MAX_NAME_LENGTH + 1))


async def test_a_refused_root_change_stores_nothing(container: AsyncContainer) -> None:
    """A refused command leaves the attribute exactly as the arrangement left it."""
    before = await load_attribute(container, BACKLIGHT)
    assert before is not None

    with pytest.raises(InvalidAttributeParentError):
        await _change(container, BACKLIGHT, _form(parent_ids=[BACKLIGHT]))

    after = await load_attribute(container, BACKLIGHT)
    assert after is not None
    assert (after.name, after.updated_at) == (before.name, before.updated_at)
