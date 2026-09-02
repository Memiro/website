from decimal import Decimal
from uuid import uuid4

import pytest
from dishka import AsyncContainer
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.common.input_limits import MAX_ATTRIBUTE_PARENTS, MAX_NAME_LENGTH
from memiro.application.errors.catalog import CategoryNotFoundError
from memiro.application.manage_attributes import CreateAttribute, CreateAttributeForm, CreatedAttribute
from memiro.entities.catalog.attribute.entity import AttributeKind
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.common.money import Money
from memiro.entities.errors.attribute import InvalidAttributeParentError, InvalidAttributeValueSetError
from tests.common.factory.catalog import BACKLIGHT, CATEGORY, CONTOUR, SECOND_CATEGORY
from tests.integration.manage_attributes.arrange import load_attribute, load_dictionary, value_form
from tests.integration.prime import prime_second_category

pytestmark = pytest.mark.usefixtures("dictionary")

# Where the owner puts the new attribute in the card: after everything the demo
# dictionary already holds.
PLACE_IN_THE_CARD = 8


@pytest.fixture
async def second_category(engine: AsyncEngine) -> None:
    """Add a section whose attributes are none of the demo dictionary's."""
    await prime_second_category(engine, name="Шкафы", slug="cabinets", sort_order=2, is_published=True)


def _form(**overrides: object) -> CreateAttributeForm:
    """Build the owner's form for a new attribute of the demo category."""
    fields: dict[str, object] = {
        "category_id": CATEGORY,
        "name": "Фацет",
        "kind": AttributeKind.SELECT,
        "parent_ids": [],
        "is_customer_changeable": True,
        "sort_order": PLACE_IN_THE_CARD,
        "values": [value_form(name="Фацет есть"), value_form(name="Без фацета", amount="0", sort_order=2)],
    }
    return CreateAttributeForm.model_validate(fields | overrides)


async def _create(container: AsyncContainer, form: CreateAttributeForm) -> CreatedAttribute:
    """Execute one creation in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(CreateAttribute)
        return await interactor.execute(form)


async def test_the_owner_creates_an_attribute_with_its_dictionary(container: AsyncContainer) -> None:
    """A new attribute is stored with every row the owner listed under it."""
    created = await _create(container, _form(parent_ids=[BACKLIGHT]))

    attribute = await load_attribute(container, created.id)
    assert attribute is not None
    assert attribute.name == "Фацет"
    assert attribute.category_id == CATEGORY
    assert attribute.parent_ids == (BACKLIGHT,)
    assert attribute.sort_order == PLACE_IN_THE_CARD
    assert [(value.name, value.rate) for value in attribute.values] == [
        ("Фацет есть", Rate(amount=Money(amount=Decimal(2500)), unit=Unit.LINEAR_METER)),
        ("Без фацета", Rate(amount=Money(amount=Decimal(0)), unit=Unit.LINEAR_METER)),
    ]


async def test_a_created_attribute_joins_the_dictionary_the_calculator_reads(container: AsyncContainer) -> None:
    """The new attribute is visible to the same gateway pricing takes the dictionary from."""
    created = await _create(container, _form())

    dictionary = await load_dictionary(container)
    assert created.id in {attribute.id for attribute in dictionary}


async def test_creating_an_attribute_fails_if_the_category_does_not_exist(container: AsyncContainer) -> None:
    """CATEGORY_NOT_FOUND: an attribute describes products of a section that exists."""
    with pytest.raises(CategoryNotFoundError):
        await _create(container, _form(category_id=uuid4()))


async def test_creating_an_attribute_fails_if_a_parent_is_not_in_the_dictionary(container: AsyncContainer) -> None:
    """INVALID_ATTRIBUTE_PARENT: dependence points at an attribute that is there."""
    with pytest.raises(InvalidAttributeParentError):
        await _create(container, _form(parent_ids=[uuid4()]))


@pytest.mark.usefixtures("second_category")
async def test_creating_an_attribute_fails_if_a_parent_belongs_to_another_category(
    container: AsyncContainer,
) -> None:
    """INVALID_ATTRIBUTE_PARENT: dependence is read inside one category and nowhere across."""
    with pytest.raises(InvalidAttributeParentError):
        await _create(container, _form(category_id=SECOND_CATEGORY, parent_ids=[BACKLIGHT]))


async def test_creating_an_attribute_fails_if_it_claims_an_existing_dictionary_row(
    container: AsyncContainer,
) -> None:
    """INVALID_ATTRIBUTE_VALUE_SET: an existing row belongs to the attribute that owns it."""
    with pytest.raises(InvalidAttributeValueSetError):
        await _create(container, _form(values=[value_form(value_id=CONTOUR)]))


async def test_creating_a_numeric_attribute_fails_with_two_tariff_rows(container: AsyncContainer) -> None:
    """INVALID_ATTRIBUTE_VALUE_SET: a numeric attribute charges by exactly one tariff."""
    with pytest.raises(InvalidAttributeValueSetError):
        await _create(container, _form(kind=AttributeKind.NUMBER))


async def test_creating_an_attribute_fails_on_a_name_one_character_over_the_limit() -> None:
    """VALIDATION_ERROR: the form refuses a name longer than the production constant allows."""
    with pytest.raises(ValidationError):
        _form(name="я" * (MAX_NAME_LENGTH + 1))


async def test_creating_an_attribute_fails_on_one_parent_over_the_limit() -> None:
    """VALIDATION_ERROR: the form refuses more parents than the production constant allows."""
    with pytest.raises(ValidationError):
        _form(parent_ids=[uuid4() for _ in range(MAX_ATTRIBUTE_PARENTS + 1)])


async def test_a_refused_creation_leaves_the_dictionary_as_it_was(container: AsyncContainer) -> None:
    """A refused command stores nothing: the dictionary holds exactly what it held."""
    before = {attribute.id for attribute in await load_dictionary(container)}

    with pytest.raises(CategoryNotFoundError):
        await _create(container, _form(category_id=uuid4()))

    assert {attribute.id for attribute in await load_dictionary(container)} == before
