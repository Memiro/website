from uuid import uuid4

import pytest
from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.errors.catalog import LandingNotFoundError, LandingSlugTakenError
from memiro.application.manage_landings import ChangeLanding, ChangeLandingForm
from memiro.entities.common.identifiers import LandingId
from memiro.entities.errors.landing import InvalidLandingNarrowingError
from tests.common.factory.catalog import ALUMINIUM, FRAME, ROUND, SHAPE
from tests.integration.manage_landings.arrange import change_form, create_form, create_landing, load_landing
from tests.integration.prime import count_landings_directly

pytestmark = pytest.mark.usefixtures("catalog")


async def _change(container: AsyncContainer, landing_id: LandingId, form: ChangeLandingForm) -> None:
    """Execute one change in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(ChangeLanding)
        await interactor.execute(landing_id, form)


async def test_the_owner_restates_the_copy_of_a_page(container: AsyncContainer) -> None:
    """The heading, the meta and the publication switch are the owner's to restate."""
    created = await create_landing(container, create_form())

    await _change(container, created.id, change_form(heading="Круглые зеркала с подсветкой", is_published=False))  # noqa: RUF001

    landing = await load_landing(container, created.id)
    assert landing is not None
    assert (landing.heading, landing.is_published) == ("Круглые зеркала с подсветкой", False)  # noqa: RUF001


async def test_the_narrowing_is_replaced_whole(container: AsyncContainer) -> None:
    """The set of conditions is one command: what the card does not carry is gone."""
    created = await create_landing(container, create_form())

    await _change(container, created.id, change_form(conditions=[ALUMINIUM]))

    landing = await load_landing(container, created.id)
    assert landing is not None
    assert [(condition.attribute_id, condition.value_id) for condition in landing.conditions] == [(FRAME, ALUMINIUM)]


async def test_a_page_nobody_entered_is_refused(container: AsyncContainer) -> None:
    """LANDING_NOT_FOUND: the card names a page this storefront holds."""
    created = await create_landing(container, create_form())
    await _change(container, created.id, change_form())

    with pytest.raises(LandingNotFoundError):
        await _change(container, uuid4(), change_form())


async def test_the_address_of_another_page_is_refused(container: AsyncContainer) -> None:
    """LANDING_SLUG_TAKEN: an address the owner frees on one page is not free on another."""
    first = await create_landing(container, create_form())
    await create_landing(container, create_form(slug="figurnye-zerkala", heading="Фигурные зеркала"))

    with pytest.raises(LandingSlugTakenError):
        await _change(container, first.id, change_form(slug="figurnye-zerkala"))


async def test_a_page_keeps_its_own_address(container: AsyncContainer) -> None:
    """The address a page already answers on is not taken from it by its own save."""
    created = await create_landing(container, create_form())

    await _change(container, created.id, change_form(title="Круглые зеркала — memiro"))

    landing = await load_landing(container, created.id)
    assert landing is not None
    assert landing.title == "Круглые зеркала — memiro"


async def test_a_refused_change_leaves_the_page_as_it_was(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """A business refusal writes nothing: the page keeps the copy and the narrowing it had."""
    created = await create_landing(container, create_form())

    with pytest.raises(InvalidLandingNarrowingError):
        await _change(container, created.id, change_form(heading="Другое", conditions=[]))

    landing = await load_landing(container, created.id)
    assert landing is not None
    assert (landing.heading, [condition.value_id for condition in landing.conditions]) == (
        "Круглые зеркала",
        [ROUND],
    )
    assert await count_landings_directly(engine) == 1
    assert landing.conditions[0].attribute_id == SHAPE
