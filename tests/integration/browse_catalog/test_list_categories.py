import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.browse_catalog import CategoriesList, CategoryModel
from tests.common.factory.catalog import SECOND_PRODUCT, THIRD_PRODUCT
from tests.integration.api_client import ApiClient
from tests.integration.prime import CATALOG_STAMP, prime_photograph, prime_priced_neighbours, prime_second_category

pytestmark = pytest.mark.usefixtures("catalog")


async def test_a_category_holding_a_published_product_is_listed(api_client: ApiClient) -> None:
    """The storefront receives its categories inside the list envelope."""
    assert (await api_client.list_categories()).assert_status(status.HTTP_200_OK).ensure_content() == CategoriesList(
        items=[CategoryModel(name="Mirrors", slug="mirrors", updated_at=CATALOG_STAMP)], total=1, page=1
    )


async def test_a_category_without_a_published_product_is_hidden(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A category whose only product is unpublished never reaches the storefront."""
    await prime_second_category(engine, name="Шкафы", slug="cabinets", sort_order=0, is_published=False)

    assert (await api_client.list_categories()).assert_status(status.HTTP_200_OK).ensure_content() == CategoriesList(
        items=[CategoryModel(name="Mirrors", slug="mirrors", updated_at=CATALOG_STAMP)], total=1, page=1
    )


async def test_categories_follow_the_order_the_owner_gave_them(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A category the owner ordered first is listed before the canonical one."""
    await prime_second_category(engine, name="Шкафы", slug="cabinets", sort_order=0, is_published=True)

    assert (await api_client.list_categories()).assert_status(status.HTTP_200_OK).ensure_content() == CategoriesList(
        items=[
            CategoryModel(name="Шкафы", slug="cabinets", updated_at=CATALOG_STAMP),
            CategoryModel(name="Mirrors", slug="mirrors", updated_at=CATALOG_STAMP),
        ],
        total=2,
        page=1,
    )


async def test_a_listed_category_carries_the_day_it_was_last_edited(api_client: ApiClient) -> None:
    """The sitemap dates a category page by this stamp, so the listing has to carry it."""
    listing = (await api_client.list_categories()).assert_status(status.HTTP_200_OK).ensure_content()

    assert listing.items[0].updated_at == CATALOG_STAMP


async def test_a_category_tile_shows_a_mirror_of_that_very_category(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A tile stands for what it leads to: the first photo of the cheapest published product."""
    await prime_priced_neighbours(engine)
    await prime_photograph(engine, "dear-front.jpg", product_id=THIRD_PRODUCT)
    await prime_photograph(engine, "cheap-side.jpg", product_id=SECOND_PRODUCT, sort_order=2)
    await prime_photograph(engine, "cheap-front.jpg", product_id=SECOND_PRODUCT, sort_order=1)

    listing = (await api_client.list_categories()).assert_status(status.HTTP_200_OK).ensure_content()

    assert listing.items[0].image is not None
    assert listing.items[0].image.key == "cheap-front.jpg"


async def test_the_photograph_of_a_tile_does_not_move_with_the_products(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """The home page looks the same from one day to the next: only the price decides."""
    await prime_priced_neighbours(engine)
    await prime_photograph(engine, "cheap-front.jpg", product_id=SECOND_PRODUCT)

    before = (await api_client.list_categories()).assert_status(status.HTTP_200_OK).ensure_content()
    await prime_photograph(engine, "dear-front.jpg", product_id=THIRD_PRODUCT)
    after = (await api_client.list_categories()).assert_status(status.HTTP_200_OK).ensure_content()

    assert before.items[0].image == after.items[0].image


async def test_a_category_without_photographs_carries_none(api_client: ApiClient) -> None:
    """A category nobody photographed yet answers with nothing, and the storefront draws its placeholder."""
    listing = (await api_client.list_categories()).assert_status(status.HTTP_200_OK).ensure_content()

    assert listing.items[0].image is None
