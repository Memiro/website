from decimal import Decimal

import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.browse_catalog import ProductsList
from memiro.application.browse_catalog.models import ProductSummary
from tests.integration.api_client import ApiClient
from tests.integration.prime import (
    prime_extra_product,
    prime_product_images,
    prime_product_publication,
    prime_second_category,
)

pytestmark = pytest.mark.usefixtures("catalog")

CANONICAL_SUMMARY = ProductSummary(name="Зеркало в раме", slug="zerkalo-v-rame", price_from=None, image_keys=[])
ARCHED_SUMMARY = ProductSummary(name="Арочное зеркало", slug="arochnoe-zerkalo", price_from=None, image_keys=[])


async def test_a_category_lists_its_published_products(
    api_client: ApiClient,
    engine: AsyncEngine,
    variants: None,  # noqa: ARG001
) -> None:
    """A listing carries the stored derived price and the photo keys inside the list envelope."""
    await prime_product_images(engine)

    assert (await api_client.list_category_products("mirrors")).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == ProductsList(
        items=[
            ProductSummary(
                name="Зеркало в раме",
                slug="zerkalo-v-rame",
                # The cheaper of the two variants added by the fixture.
                price_from=Decimal(2700),
                image_keys=["mirror-side.jpg", "mirror-front.jpg"],
            )
        ],
        total=1,
        page=1,
    )


async def test_an_unpublished_product_is_left_out_of_its_category_listing(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A category showing one of its two products lists the published one alone."""
    await prime_extra_product(engine, name="Арочное зеркало", slug="arochnoe-zerkalo", is_published=False)

    assert (await api_client.list_category_products("mirrors")).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == ProductsList(items=[CANONICAL_SUMMARY], total=1, page=1)


async def test_a_category_whose_products_are_all_unpublished_lists_nothing(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """An existing category with nothing published answers with an empty page, not a miss."""
    await prime_product_publication(engine, is_published=False)

    assert (await api_client.list_category_products("mirrors")).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == ProductsList(items=[], total=0, page=1)


async def test_a_listing_holds_no_product_of_another_category(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A published product hanging on another category stays out of this category's page."""
    await prime_second_category(engine, name="Шкафы", slug="cabinets", sort_order=2, is_published=True)

    assert (await api_client.list_category_products("mirrors")).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == ProductsList(items=[CANONICAL_SUMMARY], total=1, page=1)


async def test_products_are_listed_by_name(api_client: ApiClient, engine: AsyncEngine) -> None:
    """A category page is ordered by product name, so the arched mirror comes before the framed one."""
    await prime_extra_product(engine, name="Арочное зеркало", slug="arochnoe-zerkalo", is_published=True)

    assert (await api_client.list_category_products("mirrors")).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == ProductsList(items=[ARCHED_SUMMARY, CANONICAL_SUMMARY], total=2, page=1)


async def test_listing_fails_if_the_category_slug_belongs_to_no_category(api_client: ApiClient) -> None:
    """A slug that resolves to no category is rejected with CATEGORY_NOT_FOUND."""
    (await api_client.list_category_products("no-such-category")).assert_error(
        status.HTTP_404_NOT_FOUND, "CATEGORY_NOT_FOUND"
    )
