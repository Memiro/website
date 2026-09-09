"""Repricing from the admin: by the event of a save, and by the action on the list of products (ADR-0014).

The handler runs synchronously in the request that saved the tariff, in the
thread of the bridge (decision 6), so the owner sees the banner and the fresh
prices without leaving the screen.
"""

from collections.abc import AsyncIterator, Iterator
from decimal import Decimal
from http import HTTPStatus

import pytest
from django.test import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from memiro.entities.catalog.attribute.rate import Unit
from memiro.entities.common.identifiers import AttributeValueId, VariantId
from memiro.entities.pricing.pricing_settings import PRICING_SETTINGS_ID
from memiro.presentation.django_admin.writes import REPRICE_FAILED, REPRICED
from tests.common.factory.catalog import PRODUCT, WITH_MOUNT
from tests.integration.admin.arrange import (
    PricingBounds,
    arranged_variant,
    priced_list_post,
    priced_row,
    pricing_post,
    removed_variant,
    tier,
)
from tests.integration.prime import prime_no_pricing_settings, prime_pricing_settings, prime_size_surcharge

pytestmark = pytest.mark.usefixtures("admin_site", "primed_catalog")

APP = "memiro"
MATERIALS_URL = f"/admin/{APP}/attributevalue/"
PRODUCTS_URL = f"/admin/{APP}/product/"
PRICING_URL = f"/admin/{APP}/pricingsettings/{PRICING_SETTINGS_ID}/change/"
REPRICE_ACTION = "reprice_products"

# The bounds and the tier the demo site is left at: the screen restates the
# whole aggregate, so a save that changes nothing still publishes its event.
KEPT_BOUNDS = PricingBounds(min_area="0.35", min_order_total="3000", max_long_side_mm=3200, max_short_side_mm=2500)
KEPT_TIER = tier(from_long_side_mm=2200, factor="1.25")

# A tariff each test moves to a price of its own: the flat list sends a command
# only for a row the owner actually changed, and the admin database is shared.
DEARER_MOUNT = "1500"
REPRICED_MOUNT = "1600"
REFUSED_MOUNT = "1700"
PRICE_AT_THE_REPRICED_MOUNT = Decimal(9920)
ONE_PRODUCT = REPRICED.format(count=1)
NO_PRODUCTS = REPRICED.format(count=0)


@pytest.fixture
async def catalogue_without_pricing_settings(admin_database_url: str) -> AsyncIterator[None]:
    """Take the bounds of calculation away, so the after-commit reprice really refuses, and put them back."""
    engine = create_async_engine(admin_database_url)
    try:
        await prime_no_pricing_settings(engine)
        yield
    finally:
        await prime_pricing_settings(engine)
        await prime_size_surcharge(engine)
        await engine.dispose()


@pytest.fixture
def priced_variant() -> Iterator[VariantId]:
    """Give the demo product the one precalculated variant a reprice can move."""
    variant_id = arranged_variant(width_mm=800, height_mm=600)
    yield variant_id
    removed_variant(variant_id)


async def test_the_owner_is_told_how_many_products_the_saved_tariff_repriced(
    owner_client: AsyncClient,
    priced_variant: VariantId,  # noqa: ARG001  # the fixture is the arrangement, not a value
) -> None:
    """The banner of the after-commit reprice names the number of products behind it."""
    response = await owner_client.post(
        MATERIALS_URL,
        priced_list_post([priced_row(value_id=WITH_MOUNT, amount=DEARER_MOUNT, unit=Unit.PIECE)]),
        follow=True,
    )

    assert response.status_code == HTTPStatus.OK
    assert ONE_PRODUCT in response.content.decode()


async def test_the_owner_reprices_the_catalogue_from_the_list_of_products(
    owner_client: AsyncClient,
    priced_variant: VariantId,  # noqa: ARG001  # the fixture is the arrangement, not a value
) -> None:
    """The action on the changelist calls the very handler the events call."""
    response = await owner_client.post(
        PRODUCTS_URL,
        {"action": REPRICE_ACTION, "_selected_action": [str(PRODUCT)], "index": "0"},
        follow=True,
    )

    assert response.status_code == HTTPStatus.OK
    assert ONE_PRODUCT in response.content.decode()


async def test_the_action_answers_the_owner_even_when_it_moved_nothing(owner_client: AsyncClient) -> None:
    """A catalogue with nothing precalculated still gets its banner: silence would read as a dead action."""
    response = await owner_client.post(
        PRODUCTS_URL,
        {"action": REPRICE_ACTION, "_selected_action": [str(PRODUCT)], "index": "0"},
        follow=True,
    )

    assert response.status_code == HTTPStatus.OK
    assert NO_PRODUCTS in response.content.decode()


async def test_the_price_of_the_variant_follows_the_tariff_the_owner_saved(
    owner_client: AsyncClient,
    priced_variant: VariantId,
) -> None:
    """The owner leaves the screen with the recalculated price already stored."""
    await owner_client.post(
        MATERIALS_URL,
        priced_list_post([priced_row(value_id=WITH_MOUNT, amount=REPRICED_MOUNT, unit=Unit.PIECE)]),
    )

    assert await _price_of(priced_variant) == PRICE_AT_THE_REPRICED_MOUNT


async def test_saved_calculation_parameters_reprice_the_catalogue_too(
    owner_client: AsyncClient,
    priced_variant: VariantId,  # noqa: ARG001  # the fixture is the arrangement, not a value
) -> None:
    """The second screen that publishes an event gets the same banner from the same handler."""
    response = await owner_client.post(
        PRICING_URL,
        pricing_post(bounds=KEPT_BOUNDS, tiers=[KEPT_TIER]),
        follow=True,
    )

    assert response.status_code == HTTPStatus.OK
    assert ONE_PRODUCT in response.content.decode()


async def test_a_refused_reprice_is_a_banner_and_not_a_lost_tariff(
    owner_client: AsyncClient,
    priced_variant: VariantId,  # noqa: ARG001  # the fixture is the arrangement, not a value
    catalogue_without_pricing_settings: None,  # noqa: ARG001  # the fixture is the arrangement, not a value
) -> None:
    """The subscriber refused for want of parameters: the tariff stays saved and the owner is told why."""
    response = await owner_client.post(
        MATERIALS_URL,
        priced_list_post([priced_row(value_id=WITH_MOUNT, amount=REFUSED_MOUNT, unit=Unit.PIECE)]),
        follow=True,
    )

    assert response.status_code == HTTPStatus.OK
    assert REPRICE_FAILED in response.content.decode()
    assert await _amount_of(WITH_MOUNT) == Decimal(REFUSED_MOUNT)


async def _amount_of(value_id: AttributeValueId) -> Decimal:
    """Read the tariff of one dictionary row back through the mirror the admin reads."""
    from django.apps import apps  # noqa: PLC0415  # the app registry is only ready once Django is configured

    value = await apps.get_model(APP, "AttributeValue").objects.aget(id=value_id)
    return Decimal(value.rate_amount)


async def _price_of(variant_id: VariantId) -> Decimal:
    """Read the stored price of one variant through the mirror the admin reads."""
    from django.apps import apps  # noqa: PLC0415  # the app registry is only ready once Django is configured

    variant = await apps.get_model(APP, "ProductVariant").objects.aget(id=variant_id)
    return Decimal(variant.price)
