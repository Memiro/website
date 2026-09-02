import asyncio

import pytest
from dishka import AsyncContainer

from memiro.application.errors.catalog import AttributeNotFoundError
from memiro.application.manage_attributes import RemoveAttribute, ReplaceValues, ReplaceValuesForm
from memiro.entities.common.identifiers import AttributeId
from memiro.entities.errors.attribute import InvalidAttributeValueSetError
from tests.common.factory.catalog import HEATING, NO_HEATING, WITH_HEATING
from tests.integration.manage_attributes.arrange import load_attribute, value_form

pytestmark = pytest.mark.usefixtures("dictionary")


async def _replace(container: AsyncContainer, attribute_id: AttributeId, form: ReplaceValuesForm) -> None:
    """Execute one dictionary replacement in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(ReplaceValues)
        await interactor.execute(attribute_id, form)


async def _remove(container: AsyncContainer, attribute_id: AttributeId) -> None:
    """Execute one removal in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(RemoveAttribute)
        await interactor.execute(attribute_id)


async def test_concurrent_replacements_leave_one_dictionary_behind(container: AsyncContainer) -> None:
    """Two owners dropping different rows at once: the loser is refused, and the winner's set stands."""
    outcomes = await asyncio.gather(
        _replace(
            container, HEATING, ReplaceValuesForm(values=[value_form(value_id=WITH_HEATING, name="Подогрев есть")])
        ),
        _replace(container, HEATING, ReplaceValuesForm(values=[value_form(value_id=NO_HEATING, name="Без подогрева")])),
        return_exceptions=True,
    )

    refusals = [outcome for outcome in outcomes if isinstance(outcome, InvalidAttributeValueSetError)]
    attribute = await load_attribute(container, HEATING)
    assert len(refusals) == 1
    assert attribute is not None
    assert len(attribute.values) == 1


async def test_concurrent_removals_of_one_attribute_leave_one_refusal(container: AsyncContainer) -> None:
    """Two owners removing one attribute at once: it goes once, and the loser is told it is gone."""
    outcomes = await asyncio.gather(
        _remove(container, HEATING),
        _remove(container, HEATING),
        return_exceptions=True,
    )

    refusals = [outcome for outcome in outcomes if isinstance(outcome, AttributeNotFoundError)]
    assert len(refusals) == 1
    assert await load_attribute(container, HEATING) is None
