from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import pytest
from dishka import AsyncContainer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.adapters.db.tables import inquiry_items_table
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.application.submit_inquiry import InquiryItemForm, InquirySource, SubmitInquiryForm
from memiro.entities.common.money import Money
from tests.common.factory.catalog import PRODUCT, WITH_MOUNT
from tests.integration.api_client import ApiClient
from tests.integration.prime import (
    prime_no_pricing_settings,
    prime_product_without_paid_values,
    update_attribute_value_rate_directly,
)
from tests.integration.reprice_products.arrange import arranged_variant, load_product, prices_after, reprice

pytestmark = pytest.mark.usefixtures("catalog")

# What the workbook says the demo mirror costs, before and after the owner
# triples the price of a mount (§14.6.7 — hardcoded, never re-derived).
SMALL_BEFORE = Money(amount=Decimal(8820))
SMALL_AFTER = Money(amount=Decimal(9820))
LARGE_AFTER = Money(amount=Decimal(13020))
MOUNT_AFTER = Money(amount=Decimal(1500))


async def _inquiry_items_directly(engine: AsyncEngine) -> Sequence[Any]:
    """Read the stored positions of every inquiry, snapshot columns included."""
    async with engine.begin() as connection:
        result = await connection.execute(select(inquiry_items_table).order_by(inquiry_items_table.c.id))
        return result.mappings().all()


async def test_the_owner_reprices_a_variant_whose_tariff_moved(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """A mount that costs a thousand more makes the stored variant cost a thousand more."""
    await arranged_variant(container, width_mm=800, height_mm=600)
    await update_attribute_value_rate_directly(engine, WITH_MOUNT, MOUNT_AFTER)

    repriced = await reprice(container)

    assert repriced == 1
    assert await prices_after(container) == (SMALL_AFTER,)


async def test_the_price_from_follows_the_cheapest_variant_of_a_repriced_product(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """«Цена от» is derived by the same command that repriced the children, last."""
    await arranged_variant(container, width_mm=800, height_mm=600, sort_order=1)
    await arranged_variant(container, width_mm=1000, height_mm=800, sort_order=2)
    await update_attribute_value_rate_directly(engine, WITH_MOUNT, MOUNT_AFTER)

    await reprice(container)

    product = await load_product(container)
    assert tuple(variant.price for variant in product.variants) == (SMALL_AFTER, LARGE_AFTER)
    assert product.price_from == SMALL_AFTER


async def test_a_reprice_leaves_a_price_the_owner_typed_alone(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """A price the owner typed is not one the reprice derived, so it keeps it (ADR-0017)."""
    await arranged_variant(container, width_mm=800, height_mm=600, manual_price=Decimal(24000))
    await update_attribute_value_rate_directly(engine, WITH_MOUNT, MOUNT_AFTER)

    repriced = await reprice(container)

    assert repriced == 0
    assert await prices_after(container) == (Money(amount=Decimal(24000)),)


async def test_a_reprice_moves_the_calculated_variant_beside_a_hand_priced_one(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """One product holds both kinds of price, and only the calculated one moves (ADR-0017)."""
    await arranged_variant(container, width_mm=800, height_mm=600, sort_order=1)
    await arranged_variant(container, width_mm=1000, height_mm=800, sort_order=2, manual_price=Decimal(24000))
    await update_attribute_value_rate_directly(engine, WITH_MOUNT, MOUNT_AFTER)

    repriced = await reprice(container)

    assert repriced == 1
    assert await prices_after(container) == (SMALL_AFTER, Money(amount=Decimal(24000)))


async def test_a_catalogue_without_variants_reprices_nothing(container: AsyncContainer) -> None:
    """A product with no precalculated variant has no price to derive, and is not counted."""
    repriced = await reprice(container)

    assert repriced == 0


async def test_a_reprice_leaves_the_snapshot_of_an_inquiry_position_alone(
    container: AsyncContainer,
    engine: AsyncEngine,
    api_client: ApiClient,
) -> None:
    """ADR-0009: a position keeps the configuration and the price it was sent with."""
    await arranged_variant(container, width_mm=800, height_mm=600)
    (
        await api_client.submit_inquiry(
            SubmitInquiryForm(
                source=InquirySource.SELECTION,
                name="Anna",
                phone="+79990000000",
                email=None,
                consent=True,
                comment="",
                items=[InquiryItemForm(product_id=PRODUCT, width_mm=800, height_mm=600, selections=[], wish="")],
            )
        )
    ).ensure_content()
    stored = await _inquiry_items_directly(engine)
    await update_attribute_value_rate_directly(engine, WITH_MOUNT, MOUNT_AFTER)

    await reprice(container)

    assert await _inquiry_items_directly(engine) == stored
    assert await prices_after(container) == (SMALL_AFTER,)


async def test_a_variant_that_lost_its_paid_values_keeps_the_price_it_had(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """A configuration that stopped being calculable is left alone rather than zeroed."""
    await arranged_variant(container, width_mm=800, height_mm=600)
    await prime_product_without_paid_values(engine)

    repriced = await reprice(container)

    assert repriced == 0
    assert await prices_after(container) == (SMALL_BEFORE,)


async def test_repricing_before_the_pricing_setup_is_refused(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """PRICING_SETTINGS_NOT_FOUND: without the bounds of calculation no variant has a price."""
    await arranged_variant(container, width_mm=800, height_mm=600)
    await prime_no_pricing_settings(engine)

    with pytest.raises(PricingSettingsNotFoundError):
        await reprice(container)

    assert await prices_after(container) == (SMALL_BEFORE,)
