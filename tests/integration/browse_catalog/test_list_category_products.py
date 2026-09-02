from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.browse_catalog import CatalogQuery, CatalogSort, ProductsList
from memiro.application.browse_catalog.models import (
    FilterGroup,
    FilterOption,
    PriceBounds,
    ProductSummary,
)
from memiro.entities.catalog.attribute.entity import AttributeKind
from memiro.entities.common.identifiers import AttributeValueId
from tests.common.factory.catalog import (
    ALUMINIUM,
    NO_BACKLIGHT,
    NO_FRAME,
    RECTANGULAR,
    ROUND,
    SILVER,
    WITH_MOUNT,
    demo_attributes,
)
from tests.integration.api_client import ApiClient
from tests.integration.prime import (
    prime_extra_product,
    prime_numeric_catalog,
    prime_priced_neighbours,
    prime_product_images,
    prime_product_publication,
    prime_second_category,
)

pytestmark = pytest.mark.usefixtures("catalog")

CANONICAL_SUMMARY = ProductSummary(name="Зеркало в раме", slug="zerkalo-v-rame", price_from=None, image_keys=[])
ARCHED_SUMMARY = ProductSummary(name="Арочное зеркало", slug="arochnoe-zerkalo", price_from=None, image_keys=[])
ROUND_SUMMARY = ProductSummary(
    name="Круглое зеркало",
    slug="krugloe-zerkalo",
    price_from=Decimal(4000),
    image_keys=[],
)
LARGE_SUMMARY = ProductSummary(
    name="Большое зеркало",
    slug="bolshoe-zerkalo",
    price_from=Decimal(12000),
    image_keys=[],
)
# What the canonical mirror of the fixture declares — the rows a listing of it alone counts.
CANONICAL_DECLARATIONS = {SILVER: 1, RECTANGULAR: 1, ALUMINIUM: 1, NO_BACKLIGHT: 1, WITH_MOUNT: 1}
# The whole category once the priced neighbours join it, in name order.
ALL_THREE_SLUGS = ["bolshoe-zerkalo", "zerkalo-v-rame", "krugloe-zerkalo"]


def _groups(
    counts: dict[AttributeValueId, int],
    selected: frozenset[AttributeValueId] = frozenset(),
) -> list[FilterGroup]:
    """Build the filter groups the canonical dictionary gives, with the counters a scenario expects."""
    return [
        FilterGroup(
            attribute_id=attribute.id,
            name=attribute.name,
            options=[
                FilterOption(
                    value_id=value.id,
                    name=value.name,
                    count=counts.get(value.id, 0),
                    is_selected=value.id in selected,
                )
                for value in attribute.values
            ],
        )
        for attribute in demo_attributes()
        if attribute.kind is AttributeKind.SELECT and attribute.is_customer_changeable
    ]


NO_PRICES = PriceBounds(lowest=None, highest=None, selected_min=None, selected_max=None)


def _envelope(
    items: list[ProductSummary],
    *,
    counts: dict[AttributeValueId, int],
    selected: frozenset[AttributeValueId] = frozenset(),
    price: PriceBounds = NO_PRICES,
    sort: CatalogSort = CatalogSort.NAME,
) -> ProductsList:
    """Build the whole expected page around the part a scenario changes."""
    return ProductsList(
        items=items,
        total=len(items),
        page=1,
        pages=1,
        groups=_groups(counts, selected),
        price=price,
        sort=sort,
    )


async def test_a_category_lists_its_published_products(
    api_client: ApiClient,
    engine: AsyncEngine,
    variants: None,  # noqa: ARG001
) -> None:
    """A listing carries the stored derived price and the photo keys inside the list envelope."""
    await prime_product_images(engine)

    assert (await api_client.list_category_products("mirrors")).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == _envelope(
        [
            ProductSummary(
                name="Зеркало в раме",
                slug="zerkalo-v-rame",
                # The cheaper of the two variants added by the fixture.
                price_from=Decimal(2700),
                image_keys=["mirror-side.jpg", "mirror-front.jpg"],
            )
        ],
        counts=CANONICAL_DECLARATIONS,
        price=PriceBounds(lowest=Decimal(2700), highest=Decimal(2700), selected_min=None, selected_max=None),
    )


async def test_an_unpublished_product_is_left_out_of_its_category_listing(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A category showing one of its two products lists the published one alone."""
    await prime_extra_product(engine, name="Арочное зеркало", slug="arochnoe-zerkalo", is_published=False)

    assert (await api_client.list_category_products("mirrors")).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == _envelope([CANONICAL_SUMMARY], counts=CANONICAL_DECLARATIONS)


async def test_a_category_whose_products_are_all_unpublished_lists_nothing(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """An existing category with nothing published answers with an empty page, not a miss."""
    await prime_product_publication(engine, is_published=False)

    assert (await api_client.list_category_products("mirrors")).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == _envelope([], counts={})


async def test_a_listing_holds_no_product_of_another_category(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A published product hanging on another category stays out of this category's page."""
    await prime_second_category(engine, name="Шкафы", slug="cabinets", sort_order=2, is_published=True)

    assert (await api_client.list_category_products("mirrors")).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == _envelope([CANONICAL_SUMMARY], counts=CANONICAL_DECLARATIONS)


async def test_products_are_listed_by_name(api_client: ApiClient, engine: AsyncEngine) -> None:
    """A category page is ordered by product name, so the arched mirror comes before the framed one."""
    await prime_extra_product(engine, name="Арочное зеркало", slug="arochnoe-zerkalo", is_published=True)

    assert (await api_client.list_category_products("mirrors")).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == _envelope([ARCHED_SUMMARY, CANONICAL_SUMMARY], counts=CANONICAL_DECLARATIONS)


async def test_listing_fails_if_the_category_slug_belongs_to_no_category(api_client: ApiClient) -> None:
    """A slug that resolves to no category is rejected with CATEGORY_NOT_FOUND."""
    (await api_client.list_category_products("no-such-category")).assert_error(
        status.HTTP_404_NOT_FOUND, "CATEGORY_NOT_FOUND"
    )


async def test_a_chosen_value_leaves_only_the_products_declaring_it(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """Narrowing by the round shape drops both rectangular mirrors of the category."""
    await prime_priced_neighbours(engine)

    assert (await api_client.list_category_products("mirrors", CatalogQuery(value=[ROUND]))).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == _envelope(
        [ROUND_SUMMARY],
        # The shape group counts as if nothing in it were chosen, so its
        # rectangular row still says how much it would leave.
        counts={ROUND: 1, RECTANGULAR: 2, NO_FRAME: 1},
        selected=frozenset({ROUND}),
        price=PriceBounds(lowest=Decimal(4000), highest=Decimal(12000), selected_min=None, selected_max=None),
    )


async def test_two_values_of_one_attribute_widen_the_listing(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """Round or rectangular is a wider question than either of them alone."""
    await prime_priced_neighbours(engine)

    page = (
        (await api_client.list_category_products("mirrors", CatalogQuery(value=[ROUND, RECTANGULAR])))
        .assert_status(status.HTTP_200_OK)
        .ensure_content()
    )

    assert [item.slug for item in page.items] == ["bolshoe-zerkalo", "zerkalo-v-rame", "krugloe-zerkalo"]


async def test_values_of_different_attributes_narrow_the_listing(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A rectangular mirror in an aluminium frame is both conditions at once, not either of them."""
    await prime_priced_neighbours(engine)

    page = (
        (await api_client.list_category_products("mirrors", CatalogQuery(value=[RECTANGULAR, NO_FRAME])))
        .assert_status(status.HTTP_200_OK)
        .ensure_content()
    )

    assert page.items == []


async def test_a_value_that_belongs_to_no_attribute_of_the_category_is_dropped(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """An old link with a stranger's value stays a page of the category instead of an empty one."""
    await prime_priced_neighbours(engine)

    page = (
        (await api_client.list_category_products("mirrors", CatalogQuery(value=[uuid4()])))
        .assert_status(status.HTTP_200_OK)
        .ensure_content()
    )

    assert [item.slug for item in page.items] == ["bolshoe-zerkalo", "zerkalo-v-rame", "krugloe-zerkalo"]


async def test_a_price_range_drops_a_product_that_has_no_price(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """Asked for mirrors from 5 000 ₽, the page cannot answer with one whose price is unknown."""
    await prime_priced_neighbours(engine)

    page = (
        (await api_client.list_category_products("mirrors", CatalogQuery(price_min=Decimal(5000))))
        .assert_status(status.HTTP_200_OK)
        .ensure_content()
    )

    assert [item.slug for item in page.items] == ["bolshoe-zerkalo"]


async def test_the_cheapest_first_order_puts_a_priceless_product_last(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A mirror the site cannot price yet is not the cheapest one — it is the one without an answer."""
    await prime_priced_neighbours(engine)

    page = (
        (await api_client.list_category_products("mirrors", CatalogQuery(sort=CatalogSort.CHEAPEST)))
        .assert_status(status.HTTP_200_OK)
        .ensure_content()
    )

    assert [item.slug for item in page.items] == ["krugloe-zerkalo", "bolshoe-zerkalo", "zerkalo-v-rame"]


async def test_the_dearest_first_order_reverses_the_priced_products(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """The dearest mirror opens the page, and the priceless one still closes it."""
    await prime_priced_neighbours(engine)

    page = (
        (await api_client.list_category_products("mirrors", CatalogQuery(sort=CatalogSort.DEAREST)))
        .assert_status(status.HTTP_200_OK)
        .ensure_content()
    )

    assert [item.slug for item in page.items] == ["bolshoe-zerkalo", "krugloe-zerkalo", "zerkalo-v-rame"]


async def test_a_page_beyond_the_last_one_is_empty_without_losing_the_total(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """The second page of a one-page category is empty, and the counter still names all three mirrors."""
    await prime_priced_neighbours(engine)

    page = (
        (await api_client.list_category_products("mirrors", CatalogQuery(page=2)))
        .assert_status(status.HTTP_200_OK)
        .ensure_content()
    )

    assert page.items == []
    assert (page.total, page.pages, page.page) == (len(ALL_THREE_SLUGS), 1, 2)


async def test_a_numeric_attribute_builds_no_filter_group(api_client: ApiClient, engine: AsyncEngine) -> None:
    """Cut-outs are typed as a number, so the sidebar has no checkboxes to offer for them."""
    await prime_numeric_catalog(engine)

    page = (await api_client.list_category_products("mirrors")).assert_status(status.HTTP_200_OK).ensure_content()

    assert page.groups == []
