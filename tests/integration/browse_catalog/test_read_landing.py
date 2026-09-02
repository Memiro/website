import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.browse_catalog import CatalogQuery, LandingsList, LandingSummary
from tests.common.factory.catalog import ROUND
from tests.integration.api_client import ApiClient
from tests.integration.prime import prime_landing

pytestmark = pytest.mark.usefixtures("catalog")


async def test_a_landing_carries_the_copy_and_the_narrowing_the_owner_wrote(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A landing is the owner's page: his heading, his text and the values it stands for."""
    await prime_landing(engine)

    landing = (await api_client.read_landing("kruglye-zerkala")).assert_status(status.HTTP_200_OK).ensure_content()

    assert (landing.heading, landing.category_slug, landing.values) == ("Круглые зеркала", "mirrors", [ROUND])
    assert landing.title == "Круглые зеркала на заказ — memiro"


async def test_a_landing_narrows_the_catalogue_by_the_same_rule_the_sidebar_does(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """The values of a landing are asked of the listing exactly as a chosen filter would be."""
    await prime_landing(engine)

    landing = (await api_client.read_landing("kruglye-zerkala")).ensure_content()
    page = (
        (await api_client.list_category_products(landing.category_slug, CatalogQuery(value=landing.values)))
        .assert_status(status.HTTP_200_OK)
        .ensure_content()
    )

    assert page.items == []


async def test_a_landing_taken_off_the_storefront_answers_as_a_missing_one(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """LANDING_NOT_FOUND: the storefront does not tell a visitor that a hidden page exists."""
    await prime_landing(engine, is_published=False)

    (await api_client.read_landing("kruglye-zerkala")).assert_error(status.HTTP_404_NOT_FOUND, "LANDING_NOT_FOUND")


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
