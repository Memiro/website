import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.browse_catalog import CategoriesList, CategoryModel
from tests.integration.api_client import ApiClient
from tests.integration.prime import prime_second_category

pytestmark = pytest.mark.usefixtures("catalog")


async def test_a_category_holding_a_published_product_is_listed(api_client: ApiClient) -> None:
    """The storefront receives its categories inside the list envelope."""
    assert (await api_client.list_categories()).assert_status(status.HTTP_200_OK).ensure_content() == CategoriesList(
        items=[CategoryModel(name="Mirrors", slug="mirrors")], total=1, page=1
    )


async def test_a_category_without_a_published_product_is_hidden(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A category whose only product is unpublished never reaches the storefront."""
    await prime_second_category(engine, name="Шкафы", slug="cabinets", sort_order=0, is_published=False)

    assert (await api_client.list_categories()).assert_status(status.HTTP_200_OK).ensure_content() == CategoriesList(
        items=[CategoryModel(name="Mirrors", slug="mirrors")], total=1, page=1
    )


async def test_categories_follow_the_order_the_owner_gave_them(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A category the owner ordered first is listed before the canonical one."""
    await prime_second_category(engine, name="Шкафы", slug="cabinets", sort_order=0, is_published=True)

    assert (await api_client.list_categories()).assert_status(status.HTTP_200_OK).ensure_content() == CategoriesList(
        items=[
            CategoryModel(name="Шкафы", slug="cabinets"),
            CategoryModel(name="Mirrors", slug="mirrors"),
        ],
        total=2,
        page=1,
    )
