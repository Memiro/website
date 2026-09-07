import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.browse_catalog import CatalogQuery
from tests.common.factory.catalog import BLADE, ROUND, SILVER
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


async def test_a_landing_narrowed_by_an_unfilterable_attribute_answers_as_a_missing_one(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """LANDING_NOT_FOUND: the sidebar drops such a value, and an indexable page must not show the whole category."""
    await prime_landing(engine, narrows_by=(BLADE, SILVER))

    (await api_client.read_landing("kruglye-zerkala")).assert_error(status.HTTP_404_NOT_FOUND, "LANDING_NOT_FOUND")
