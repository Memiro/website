import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.browse_catalog import LandingsList, LandingSummary
from tests.common.factory.catalog import SECOND_PRODUCT
from tests.integration.api_client import ApiClient
from tests.integration.prime import CATALOG_STAMP, prime_landing, prime_photograph, prime_priced_neighbours

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
        items=[LandingSummary(slug="kruglye-zerkala", heading="Круглые зеркала", updated_at=CATALOG_STAMP)],
        total=1,
        page=1,
    )


async def test_a_listed_landing_carries_the_day_it_was_last_edited(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """The sitemap dates a landing by this stamp, so the tiles have to carry it."""
    await prime_landing(engine)

    listing = (await api_client.list_landings()).assert_status(status.HTTP_200_OK).ensure_content()

    assert listing.items[0].updated_at == CATALOG_STAMP


async def test_a_landing_tile_shows_a_mirror_its_own_narrowing_leaves(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """Two landings of one category do not show the same photograph: each tile keeps to its narrowing."""
    await prime_priced_neighbours(engine)
    await prime_landing(engine)
    await prime_photograph(engine, "round-front.jpg", product_id=SECOND_PRODUCT)

    listing = (await api_client.list_landings()).assert_status(status.HTTP_200_OK).ensure_content()

    assert listing.items[0].image is not None
    assert listing.items[0].image.key == "round-front.jpg"


async def test_a_landing_whose_mirrors_are_unphotographed_carries_no_photograph(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A narrowing that leaves no photographed mirror answers with nothing, not with somebody else's."""
    await prime_priced_neighbours(engine)
    await prime_landing(engine)
    await prime_photograph(engine, "rectangular-front.jpg")

    listing = (await api_client.list_landings()).assert_status(status.HTTP_200_OK).ensure_content()

    assert listing.items[0].image is None
