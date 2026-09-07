import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.browse_catalog import LandingsList, LandingSummary
from tests.integration.api_client import ApiClient
from tests.integration.prime import prime_landing

pytestmark = pytest.mark.usefixtures("catalog")


async def test_an_unpublished_landing_is_not_a_tile_either(api_client: ApiClient, engine: AsyncEngine) -> None:
    """Tiles show what the storefront publishes, and nothing else."""
    await prime_landing(engine, is_published=False)

    assert (await api_client.list_landings()).assert_status(status.HTTP_200_OK).ensure_content() == LandingsList(
        items=[], total=0, page=1
    )


async def test_the_storefront_lists_its_landings_as_tiles(api_client: ApiClient, engine: AsyncEngine) -> None:
    """A published landing reaches the tiles by its heading and its address."""
    await prime_landing(engine)

    assert (await api_client.list_landings()).assert_status(status.HTTP_200_OK).ensure_content() == LandingsList(
        items=[LandingSummary(slug="kruglye-zerkala", heading="Круглые зеркала")],
        total=1,
        page=1,
    )
