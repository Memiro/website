import asyncio
from uuid import uuid4

import pytest
from dishka import AsyncContainer
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.common.input_limits import MAX_DESCRIPTION_LENGTH, MAX_NAME_LENGTH
from memiro.application.errors.catalog import CategoryNotFoundError, ProductSlugTakenError
from memiro.application.manage_products import CreatedProduct, CreateProduct, CreateProductForm
from memiro.entities.errors.product import InvalidProductSlugError
from tests.common.factory.catalog import CATEGORY
from tests.integration.manage_products.arrange import load_product
from tests.integration.prime import count_products_directly

pytestmark = pytest.mark.usefixtures("catalog")

# The address the canonical product of the demo catalogue already answers on.
TAKEN_ADDRESS = "zerkalo-v-rame"


def _form(**overrides: object) -> CreateProductForm:
    """Build the owner's card for a new product of the demo section."""
    fields: dict[str, object] = {
        "category_id": CATEGORY,
        "name": "Зеркало с подсветкой",
        "slug": "",
        "description": "Зеркало с контурной подсветкой.",
        "is_published": True,
        "hides_calculated_price": False,
    }
    return CreateProductForm.model_validate(fields | overrides)


async def _create(container: AsyncContainer, form: CreateProductForm) -> CreatedProduct:
    """Execute one creation in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(CreateProduct)
        return await interactor.execute(form)


async def test_the_owner_enters_a_product_into_the_catalogue(container: AsyncContainer) -> None:
    """A new product is stored with every field of the card the owner filled in."""
    created = await _create(container, _form())

    product = await load_product(container, created.id)
    assert product is not None
    assert product.name == "Зеркало с подсветкой"
    assert product.category_id == CATEGORY
    assert product.description == "Зеркало с контурной подсветкой."
    assert product.is_published is True
    assert product.hides_calculated_price is False


async def test_a_new_product_takes_its_address_from_its_name(container: AsyncContainer) -> None:
    """An address left empty is transliterated from the name by the domain."""
    created = await _create(container, _form())

    product = await load_product(container, created.id)
    assert product is not None
    assert product.slug == "zerkalo-s-podsvetkoy"


async def test_a_new_product_declares_nothing_and_shows_no_price(container: AsyncContainer) -> None:
    """A product is born empty: the owner declares its values and builds its variants after."""
    created = await _create(container, _form())

    product = await load_product(container, created.id)
    assert product is not None
    assert product.declared_values == ()
    assert product.price_from is None


async def test_creating_a_product_fails_if_the_category_does_not_exist(container: AsyncContainer) -> None:
    """CATEGORY_NOT_FOUND: a product belongs to a section that exists."""
    with pytest.raises(CategoryNotFoundError):
        await _create(container, _form(category_id=uuid4()))


async def test_creating_a_product_fails_if_the_address_is_taken(container: AsyncContainer) -> None:
    """PRODUCT_SLUG_TAKEN: two products cannot answer on one public address."""
    with pytest.raises(ProductSlugTakenError):
        await _create(container, _form(slug=TAKEN_ADDRESS))


async def test_creating_a_product_fails_if_its_name_yields_no_address(container: AsyncContainer) -> None:
    """INVALID_PRODUCT_SLUG: a name of punctuation alone leaves nothing to address the card by."""
    with pytest.raises(InvalidProductSlugError):
        await _create(container, _form(name="!!!"))


async def test_creating_a_product_fails_on_a_name_one_character_over_the_limit() -> None:
    """VALIDATION_ERROR: the form refuses a name longer than the production constant allows."""
    with pytest.raises(ValidationError):
        _form(name="я" * (MAX_NAME_LENGTH + 1))


async def test_creating_a_product_fails_on_a_description_one_character_over_the_limit() -> None:
    """VALIDATION_ERROR: the form refuses a description longer than the production constant allows."""
    with pytest.raises(ValidationError):
        _form(description="я" * (MAX_DESCRIPTION_LENGTH + 1))


async def test_creating_a_product_fails_on_an_address_that_is_not_one() -> None:
    """VALIDATION_ERROR: the form refuses an address instead of silently rewriting it."""
    with pytest.raises(ValidationError):
        _form(slug="Зеркало в раме")


async def test_a_refused_creation_stores_nothing(container: AsyncContainer, engine: AsyncEngine) -> None:
    """A refused command leaves the catalogue holding exactly what it held."""
    before = await count_products_directly(engine)

    with pytest.raises(ProductSlugTakenError):
        await _create(container, _form(slug=TAKEN_ADDRESS))

    assert await count_products_directly(engine) == before


async def test_two_products_racing_for_one_address_leave_one_winner(container: AsyncContainer) -> None:
    """The unique column settles the race the check cannot see: the loser is told to retry."""
    form = _form(slug="zerkalo-bliznec")

    outcomes = await asyncio.gather(_create(container, form), _create(container, form), return_exceptions=True)

    # Either road ends the race honestly: the check sees the winner's row, or
    # the unique column refuses the loser's insert.
    assert [isinstance(outcome, CreatedProduct) for outcome in outcomes].count(True) == 1
    assert [isinstance(outcome, ProductSlugTakenError | IntegrityError) for outcome in outcomes].count(True) == 1
