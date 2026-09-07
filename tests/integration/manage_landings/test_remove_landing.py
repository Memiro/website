from uuid import uuid4

import pytest
from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.errors.catalog import LandingNotFoundError
from memiro.application.manage_landings import RemoveLanding
from memiro.entities.common.identifiers import LandingId
from tests.integration.manage_landings.arrange import create_form, create_landing, load_landing
from tests.integration.prime import count_landings_directly

pytestmark = pytest.mark.usefixtures("catalog")


async def _remove(container: AsyncContainer, landing_id: LandingId) -> None:
    """Execute one removal in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(RemoveLanding)
        await interactor.execute(landing_id)


async def test_the_owner_takes_a_page_off_the_storefront(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """Nothing holds a landing back: it goes, and its narrowing goes with it."""
    created = await create_landing(container, create_form())

    await _remove(container, created.id)

    assert await load_landing(container, created.id) is None
    assert await count_landings_directly(engine) == 0


async def test_a_page_nobody_entered_is_refused(container: AsyncContainer) -> None:
    """LANDING_NOT_FOUND: the command names a page this storefront holds."""
    with pytest.raises(LandingNotFoundError):
        await _remove(container, uuid4())


async def test_the_address_of_a_removed_page_is_free_again(container: AsyncContainer) -> None:
    """Removal frees the address; taking a page off publication does not."""
    created = await create_landing(container, create_form())
    await _remove(container, created.id)

    entered = await create_landing(container, create_form())

    assert entered.id != created.id
