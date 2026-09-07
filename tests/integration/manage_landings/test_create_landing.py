from uuid import uuid4

import pytest
from dishka import AsyncContainer
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.errors.catalog import CategoryNotFoundError, LandingSlugTakenError
from memiro.entities.errors.landing import InvalidLandingNarrowingError
from tests.common.factory.catalog import BACKLIGHT, CONTOUR, RECTANGULAR, ROUND, SHAPE, SILVER
from tests.integration.manage_landings.arrange import LANDING_SLUG, create_form, create_landing, load_landing
from tests.integration.prime import count_landings_directly

pytestmark = pytest.mark.usefixtures("catalog")


async def test_the_owner_enters_a_landing_into_the_storefront(container: AsyncContainer) -> None:
    """A new page is stored with the copy of the card and the narrowing it stands for."""
    created = await create_landing(container, create_form())

    landing = await load_landing(container, created.id)

    assert landing is not None
    assert (landing.slug, landing.heading, landing.is_published) == (LANDING_SLUG, "Круглые зеркала", True)
    assert [(condition.attribute_id, condition.value_id) for condition in landing.conditions] == [(SHAPE, ROUND)]


async def test_an_address_nobody_typed_is_transliterated_from_the_heading(container: AsyncContainer) -> None:
    """The owner writes the heading; the domain writes the address it gets."""
    created = await create_landing(container, create_form(slug="", heading="Зеркала с подсветкой"))  # noqa: RUF001

    landing = await load_landing(container, created.id)

    assert landing is not None
    assert landing.slug == "zerkala-s-podsvetkoy"


async def test_a_landing_in_an_unknown_category_is_refused(container: AsyncContainer) -> None:
    """CATEGORY_NOT_FOUND: a page narrows a category of this catalogue, not an identifier."""
    with pytest.raises(CategoryNotFoundError):
        await create_landing(container, create_form(category_id=uuid4()))


async def test_the_address_of_another_landing_is_refused(container: AsyncContainer) -> None:
    """LANDING_SLUG_TAKEN: one address answers with one page."""
    await create_landing(container, create_form())

    with pytest.raises(LandingSlugTakenError):
        await create_landing(container, create_form(heading="Круглые зеркала на заказ"))


async def test_a_page_that_narrows_by_nothing_is_refused(container: AsyncContainer) -> None:
    """INVALID_LANDING_NARROWING: without conditions the page is its category under a second address."""
    with pytest.raises(InvalidLandingNarrowingError):
        await create_landing(container, create_form(conditions=[]))


async def test_a_page_narrowed_by_an_unfilterable_attribute_is_refused(container: AsyncContainer) -> None:
    """The sidebar drops such a value, and the page would show the whole category (ADR-0003)."""
    with pytest.raises(InvalidLandingNarrowingError):
        await create_landing(container, create_form(conditions=[SILVER]))


async def test_a_page_listing_the_whole_dictionary_of_an_attribute_is_refused(container: AsyncContainer) -> None:
    """Every value of one attribute is the category itself under its own address."""
    with pytest.raises(InvalidLandingNarrowingError):
        await create_landing(container, create_form(conditions=[ROUND, RECTANGULAR]))


async def test_a_value_nobody_issued_is_refused(container: AsyncContainer) -> None:
    """A narrowing the dictionary does not hold is not a narrowing at all."""
    with pytest.raises(InvalidLandingNarrowingError):
        await create_landing(container, create_form(conditions=[uuid4()]))


async def test_a_refused_page_leaves_the_storefront_untouched(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """The transaction of a refused command stores nothing at all — not even the row of the page."""
    with pytest.raises(InvalidLandingNarrowingError):
        await create_landing(container, create_form(conditions=[]))

    assert await count_landings_directly(engine) == 0


async def test_a_card_outside_the_bounds_of_the_form_is_refused() -> None:
    """VALIDATION_ERROR: the address is latin words joined by single hyphens or nothing at all."""
    with pytest.raises(ValidationError):
        create_form(slug="Круглые Зеркала")


async def test_two_attributes_narrow_one_page(container: AsyncContainer) -> None:
    """The pages of the old site narrow by a shape and a backlight at once: OR inside, AND between."""
    created = await create_landing(container, create_form(conditions=[ROUND, CONTOUR]))

    landing = await load_landing(container, created.id)

    assert landing is not None
    assert {condition.attribute_id for condition in landing.conditions} == {SHAPE, BACKLIGHT}
