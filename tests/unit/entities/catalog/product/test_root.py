from uuid import uuid4

import pytest

from memiro.entities.catalog.product.entity import ChangeProductData, CreateProductData, product_factory
from memiro.entities.common.identifiers import CategoryId
from memiro.entities.errors.product import InvalidProductSlugError, ProductSectionNotEmptyError
from tests.clock import CLOCK, LATER, LATER_CLOCK, NOW
from tests.common.factory.catalog import CATEGORY, demo_product

OTHER_CATEGORY: CategoryId = uuid4()


def _data(  # noqa: PLR0913  # one keyword per field of the card the owner fills in
    *,
    category_id: CategoryId = CATEGORY,
    name: str = "Зеркало в раме",
    slug: str = "",
    description: str = "Зеркало под заказ.",
    is_published: bool = True,
    hides_calculated_price: bool = False,
) -> CreateProductData:
    """Build the owner's card of a new mirror as the admin submits it."""
    return CreateProductData(
        category_id=category_id,
        name=name,
        slug=slug,
        description=description,
        is_published=is_published,
        hides_calculated_price=hides_calculated_price,
    )


def test_a_new_product_is_born_at_one_reading_of_the_clock() -> None:
    """A product the owner has just entered was created and changed at the same instant."""
    product = product_factory(_data(), clock=CLOCK)

    assert product.created_at == NOW
    assert product.updated_at == NOW


def test_a_new_product_takes_its_address_from_its_name() -> None:
    """An empty address is transliterated from the name the owner typed."""
    product = product_factory(_data(), clock=CLOCK)

    assert product.slug == "zerkalo-v-rame"


def test_a_new_product_keeps_the_address_the_owner_typed() -> None:
    """An address the owner typed himself reaches storage as he typed it."""
    product = product_factory(_data(slug="mirror-in-a-frame"), clock=CLOCK)

    assert product.slug == "mirror-in-a-frame"


def test_a_new_product_shows_no_price_and_declares_nothing() -> None:
    """A product is born empty: no declarations, no variants and therefore no price."""
    product = product_factory(_data(), clock=CLOCK)

    assert product.declared_values == ()
    assert product.variants == ()
    assert product.price_from is None


def test_a_new_product_fails_if_its_name_yields_no_address() -> None:
    """INVALID_PRODUCT_SLUG: a name of punctuation alone leaves nothing to address the card by."""
    with pytest.raises(InvalidProductSlugError):
        product_factory(_data(name="!!!"), clock=CLOCK)


def _restated(  # noqa: PLR0913  # one keyword per field of the card the owner fills in
    *,
    category_id: CategoryId = CATEGORY,
    name: str = "Зеркало в раме",
    slug: str = "",
    description: str = "Зеркало под заказ.",
    is_published: bool = True,
    hides_calculated_price: bool = False,
) -> ChangeProductData:
    """Build the card that restates a stored mirror."""
    return ChangeProductData(
        category_id=category_id,
        name=name,
        slug=slug,
        description=description,
        is_published=is_published,
        hides_calculated_price=hides_calculated_price,
    )


def test_a_changed_product_takes_the_owners_new_card() -> None:
    """A change restates every owner-controlled field of the root."""
    product = demo_product()

    product.change(_restated(name="Зеркало с подсветкой", slug="mirror-led", is_published=False), clock=LATER_CLOCK)

    assert product.name == "Зеркало с подсветкой"
    assert product.slug == "mirror-led"
    assert product.is_published is False


def test_a_changed_product_notes_when_it_was_changed() -> None:
    """A change moves the product's own timestamp to the instant of the command."""
    product = demo_product()

    product.change(_restated(), clock=LATER_CLOCK)

    assert product.updated_at == LATER


def test_moving_a_product_fails_if_it_still_declares_values() -> None:
    """PRODUCT_SECTION_NOT_EMPTY: what the product answered was answered by the attributes it is leaving."""
    product = demo_product()

    with pytest.raises(ProductSectionNotEmptyError):
        product.change(_restated(category_id=OTHER_CATEGORY), clock=LATER_CLOCK)


def test_an_emptied_product_moves_to_another_section() -> None:
    """A product carrying no answers of its old section is free to join another one."""
    product = demo_product()
    product.declare_values([], clock=CLOCK)

    product.change(_restated(category_id=OTHER_CATEGORY), clock=LATER_CLOCK)

    assert product.category_id == OTHER_CATEGORY


def test_a_refused_move_leaves_the_product_in_its_section() -> None:
    """A refusal is not a half-done move: the name that came with it is not on the product either."""
    product = demo_product()

    with pytest.raises(ProductSectionNotEmptyError):
        product.change(_restated(category_id=OTHER_CATEGORY, name="Зеркало в шкафу"), clock=LATER_CLOCK)

    assert product.category_id == CATEGORY
    assert product.name == "Зеркало в раме"


def test_a_product_kept_in_its_section_keeps_what_it_declared() -> None:
    """A change that leaves the section alone leaves the declarations alone."""
    product = demo_product()
    declared = product.declared_values

    product.change(_restated(name="Зеркало в раме, широкое"), clock=LATER_CLOCK)

    assert product.declared_values == declared
