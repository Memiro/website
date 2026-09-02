from uuid import uuid4

import pytest
from dishka import AsyncContainer

from memiro.application.errors.catalog import AttributeInUseError, AttributeNotFoundError
from memiro.application.manage_attributes import RemoveAttribute
from memiro.entities.common.identifiers import AttributeId
from memiro.entities.errors.attribute import InvalidAttributeParentError
from tests.common.factory.catalog import BACKLIGHT, BLADE, HEATING, WITH_HEATING
from tests.integration.manage_attributes.arrange import load_attribute, load_dictionary

pytestmark = pytest.mark.usefixtures("dictionary")

# What the demo blade holds: silver and graphite.
BLADE_ROWS = 2


async def _remove(container: AsyncContainer, attribute_id: AttributeId) -> None:
    """Execute one removal in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(RemoveAttribute)
        await interactor.execute(attribute_id)


async def test_the_owner_removes_an_attribute_nobody_uses(container: AsyncContainer) -> None:
    """Heating is declared by no product and depended on by no attribute, so it goes."""
    await _remove(container, HEATING)

    assert await load_attribute(container, HEATING) is None


async def test_removing_an_attribute_takes_its_dictionary_with_it(container: AsyncContainer) -> None:
    """The rows are children of the aggregate: nothing of heating is left behind."""
    await _remove(container, HEATING)

    dictionary = await load_dictionary(container)
    assert WITH_HEATING not in {value.id for attribute in dictionary for value in attribute.values}


async def test_removing_an_attribute_fails_if_there_is_no_such_attribute(container: AsyncContainer) -> None:
    """ATTRIBUTE_NOT_FOUND: an identifier nobody issued names nothing."""
    with pytest.raises(AttributeNotFoundError):
        await _remove(container, uuid4())


async def test_removing_an_attribute_fails_if_another_one_depends_on_it(container: AsyncContainer) -> None:
    """INVALID_ATTRIBUTE_PARENT: heating depends on backlight, so backlight stays."""
    with pytest.raises(InvalidAttributeParentError):
        await _remove(container, BACKLIGHT)


async def test_removing_an_attribute_fails_and_names_the_products_that_declare_it(
    container: AsyncContainer,
) -> None:
    """ATTRIBUTE_IN_USE: the canonical mirror declares its blade, so the blade attribute stays."""
    with pytest.raises(AttributeInUseError) as refusal:
        await _remove(container, BLADE)

    assert refusal.value.meta == {"products": ["Зеркало в раме"]}


async def test_a_refused_removal_leaves_the_attribute_in_place(container: AsyncContainer) -> None:
    """A refused command deletes nothing: the attribute and its rows are still there."""
    with pytest.raises(AttributeInUseError):
        await _remove(container, BLADE)

    attribute = await load_attribute(container, BLADE)
    assert attribute is not None
    assert len(attribute.values) == BLADE_ROWS
