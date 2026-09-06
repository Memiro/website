import asyncio
from uuid import uuid4

import pytest
from dishka import AsyncContainer
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.common.input_limits import MAX_NAME_LENGTH
from memiro.application.errors.catalog import (
    CategoryNotFoundError,
    ProductNotFoundError,
    ProductSlugTakenError,
)
from memiro.application.manage_products import ChangeProduct, ChangeProductForm
from memiro.entities.common.identifiers import ProductId
from memiro.entities.errors.product import InvalidProductSlugError, ProductSectionNotEmptyError
from tests.common.factory.catalog import CATEGORY, PRODUCT, SECOND_CATEGORY, SECOND_PRODUCT
from tests.integration.manage_products.arrange import load_product
from tests.integration.prime import (
    prime_emptied_product,
    prime_extra_product,
    prime_second_category,
    read_address_holder_directly,
)

pytestmark = pytest.mark.usefixtures("catalog")

# The address the canonical product already answers on.
OWN_ADDRESS = "zerkalo-v-rame"


@pytest.fixture
async def neighbour(engine: AsyncEngine) -> None:
    """Give the section one more product, so an address in it is already spoken for."""
    await prime_extra_product(engine, name="Зеркало с полкой", slug="zerkalo-s-polkoy", is_published=True)


@pytest.fixture
async def second_section(engine: AsyncEngine) -> None:
    """Add a section the product can be moved into."""
    await prime_second_category(engine, name="Шкафы", slug="cabinets", sort_order=2, is_published=True)


def _form(**overrides: object) -> ChangeProductForm:
    """Build the owner's card for the canonical product."""
    fields: dict[str, object] = {
        "category_id": CATEGORY,
        "name": "Зеркало в раме",
        "slug": OWN_ADDRESS,
        "description": "Зеркало под заказ.",
        "is_published": True,
        "hides_calculated_price": False,
    }
    return ChangeProductForm.model_validate(fields | overrides)


async def _change(container: AsyncContainer, form: ChangeProductForm, product_id: ProductId = PRODUCT) -> None:
    """Execute one change in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(ChangeProduct)
        await interactor.execute(product_id, form)


async def test_the_owner_restates_the_card_of_a_product(container: AsyncContainer) -> None:
    """A change replaces every owner-controlled field of the root."""
    await _change(
        container,
        _form(
            name="Зеркало в раме, широкое",
            slug="zerkalo-shirokoe",
            description="Широкое зеркало под заказ.",
            is_published=False,
            hides_calculated_price=True,
        ),
    )

    product = await load_product(container, PRODUCT)
    assert product is not None
    assert product.name == "Зеркало в раме, широкое"
    assert product.slug == "zerkalo-shirokoe"
    assert product.description == "Широкое зеркало под заказ."
    assert product.is_published is False
    assert product.hides_calculated_price is True


async def test_a_product_emptied_of_its_address_takes_one_from_its_name(container: AsyncContainer) -> None:
    """An address the owner cleared is transliterated from the name again."""
    await _change(container, _form(name="Зеркало с подсветкой", slug=""))

    product = await load_product(container, PRODUCT)
    assert product is not None
    assert product.slug == "zerkalo-s-podsvetkoy"


async def test_a_product_keeps_the_address_it_already_answers_on(container: AsyncContainer) -> None:
    """A card resubmitted unchanged is not a product competing with itself for its own address."""
    await _change(container, _form(name="Зеркало в раме, широкое"))

    product = await load_product(container, PRODUCT)
    assert product is not None
    assert product.slug == OWN_ADDRESS


@pytest.mark.usefixtures("second_section")
async def test_moving_a_product_fails_while_it_still_declares_values(container: AsyncContainer) -> None:
    """PRODUCT_SECTION_NOT_EMPTY: what the product answered was answered by the attributes it is leaving."""
    with pytest.raises(ProductSectionNotEmptyError):
        await _change(container, _form(category_id=SECOND_CATEGORY))


@pytest.mark.usefixtures("second_section")
async def test_an_emptied_product_moves_to_another_section(container: AsyncContainer, engine: AsyncEngine) -> None:
    """A product the owner has cleared is free to join another section."""
    await prime_emptied_product(engine)

    await _change(container, _form(category_id=SECOND_CATEGORY))

    product = await load_product(container, PRODUCT)
    assert product is not None
    assert product.category_id == SECOND_CATEGORY


async def test_a_product_kept_in_its_section_keeps_what_it_declared(container: AsyncContainer) -> None:
    """A change that leaves the section alone leaves the declarations alone."""
    before = await load_product(container, PRODUCT)
    assert before is not None

    await _change(container, _form(name="Зеркало в раме, широкое"))

    product = await load_product(container, PRODUCT)
    assert product is not None
    assert product.declared_values == before.declared_values


@pytest.mark.usefixtures("neighbour")
async def test_two_products_racing_for_one_address_leave_one_winner(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """The unique column settles the race the check cannot see: only one product ends up on the address."""
    contested = _form(slug="zerkalo-spornoe")

    outcomes = await asyncio.gather(
        _change(container, contested),
        _change(container, contested, product_id=SECOND_PRODUCT),
        return_exceptions=True,
    )

    assert sorted(outcome is None for outcome in outcomes) == [False, True]
    assert await read_address_holder_directly(engine, "zerkalo-spornoe") is not None


async def test_changing_a_product_fails_if_it_does_not_exist(container: AsyncContainer) -> None:
    """PRODUCT_NOT_FOUND: a card names a product that exists."""
    with pytest.raises(ProductNotFoundError):
        await _change(container, _form(), product_id=uuid4())


async def test_changing_a_product_fails_if_the_new_section_does_not_exist(container: AsyncContainer) -> None:
    """CATEGORY_NOT_FOUND: a product is moved into a section that exists."""
    with pytest.raises(CategoryNotFoundError):
        await _change(container, _form(category_id=uuid4()))


@pytest.mark.usefixtures("neighbour")
async def test_changing_a_product_fails_if_the_address_belongs_to_another(container: AsyncContainer) -> None:
    """PRODUCT_SLUG_TAKEN: two products cannot answer on one public address."""
    with pytest.raises(ProductSlugTakenError):
        await _change(container, _form(slug="zerkalo-s-polkoy"))


async def test_changing_a_product_fails_if_its_name_yields_no_address(container: AsyncContainer) -> None:
    """INVALID_PRODUCT_SLUG: a name of punctuation alone leaves nothing to address the card by."""
    with pytest.raises(InvalidProductSlugError):
        await _change(container, _form(name="!!!", slug=""))


async def test_changing_a_product_fails_on_a_name_one_character_over_the_limit() -> None:
    """VALIDATION_ERROR: the form refuses a name longer than the production constant allows."""
    with pytest.raises(ValidationError):
        _form(name="я" * (MAX_NAME_LENGTH + 1))


@pytest.mark.usefixtures("neighbour")
async def test_a_refused_change_leaves_the_product_as_it_was(container: AsyncContainer) -> None:
    """A refused command stores nothing: the name the refusal came with is not on the product."""
    with pytest.raises(ProductSlugTakenError):
        await _change(container, _form(name="Не сохранится", slug="zerkalo-s-polkoy"))

    product = await load_product(container, PRODUCT)
    assert product is not None
    assert product.name == "Зеркало в раме"
