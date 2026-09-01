"""Integration checks for the SQLAlchemy Product gateway."""

import json
from decimal import Decimal

import pytest
from dishka import AsyncContainer
from fastapi import FastAPI
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.adapters.db.tables import product_variants_table
from memiro.application.common.gateway.product import ProductGateway
from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.catalog.product.entity import DeclaredValue, VariantData
from memiro.entities.common.identifiers import VariantId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro_common.uow import UoW
from tests.common.factory.catalog import BLADE, CUTOUTS, PRODUCT, SILVER

pytestmark = pytest.mark.usefixtures("catalog")


def _variant_data() -> VariantData:
    """Build the canonical workbook size without overrides."""
    return VariantData(
        dimensions=Dimensions(
            width=Millimeters(value=800),
            height=Millimeters(value=600),
        ),
        overrides=(
            DeclaredValue(
                attribute_id=BLADE,
                chosen=ChosenValue(value_id=SILVER, quantity=None),
            ),
            DeclaredValue(
                attribute_id=CUTOUTS,
                chosen=ChosenValue(value_id=None, quantity=Decimal("2.50")),
            ),
        ),
        sort_order=3,
    )


async def _corrupt_fingerprint(engine: AsyncEngine, variant_id: VariantId) -> None:
    """Break the stored integrity guard through the named dishonest-state seam."""
    async with engine.begin() as connection:
        await connection.execute(
            update(product_variants_table).where(product_variants_table.c.id == variant_id).values(fingerprint=PRODUCT),
        )


async def _corrupt_overrides(
    engine: AsyncEngine,
    variant_id: VariantId,
    *,
    overrides: list[dict[str, str | None]],
) -> None:
    """Store invalid overrides through the named dishonest-state seam."""
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """UPDATE product_variants
                   SET overrides = CAST(:overrides AS jsonb)
                   WHERE id = :variant_id"""
            ),
            {
                "overrides": json.dumps(overrides),
                "variant_id": variant_id,
            },
        )


async def test_the_product_gateway_round_trips_variants_and_the_derived_price(
    app: FastAPI,
) -> None:
    """The gateway persists the whole Product aggregate with its derived price."""
    container: AsyncContainer = app.state.dishka_container
    async with container() as request:
        gateway = await request.get(ProductGateway)
        uow = await request.get(UoW)
        product = await gateway.get(PRODUCT, for_update=True, eager_variants=True)
        assert product is not None
        product.add_variant(_variant_data(), price=Money(amount=Decimal(8900)))
        await uow.commit()
    async with container() as request:
        gateway = await request.get(ProductGateway)
        loaded = await gateway.get(PRODUCT, eager_variants=True)

    assert loaded == product


async def test_the_product_gateway_refuses_a_corrupted_variant_fingerprint(
    app: FastAPI,
    engine: AsyncEngine,
) -> None:
    """A stored uniqueness key that disagrees with the child fails loudly."""
    container: AsyncContainer = app.state.dishka_container
    async with container() as request:
        gateway = await request.get(ProductGateway)
        uow = await request.get(UoW)
        product = await gateway.get(PRODUCT, for_update=True, eager_variants=True)
        assert product is not None
        variant = product.add_variant(_variant_data(), price=Money(amount=Decimal(8900)))
        await uow.commit()
    await _corrupt_fingerprint(engine, variant.id)

    async with container() as request:
        gateway = await request.get(ProductGateway)

        with pytest.raises(RuntimeError, match="fingerprint"):
            await gateway.get(PRODUCT, eager_variants=True)


async def test_the_product_gateway_refuses_corrupted_variant_overrides(
    app: FastAPI,
    engine: AsyncEngine,
) -> None:
    """An incomplete stored override is treated as a system defect."""
    container: AsyncContainer = app.state.dishka_container
    async with container() as request:
        gateway = await request.get(ProductGateway)
        uow = await request.get(UoW)
        product = await gateway.get(PRODUCT, for_update=True, eager_variants=True)
        assert product is not None
        variant = product.add_variant(_variant_data(), price=Money(amount=Decimal(8900)))
        await uow.commit()
    await _corrupt_overrides(
        engine,
        variant.id,
        overrides=[{"attribute_id": str(BLADE), "value_id": None, "quantity": None}],
    )

    async with container() as request:
        gateway = await request.get(ProductGateway)

        with pytest.raises(RuntimeError, match="corrupted variant overrides"):
            await gateway.get(PRODUCT, eager_variants=True)


async def test_the_product_gateway_refuses_malformed_variant_override_data(
    app: FastAPI,
    engine: AsyncEngine,
) -> None:
    """A malformed stored override is treated as a system defect."""
    container: AsyncContainer = app.state.dishka_container
    async with container() as request:
        gateway = await request.get(ProductGateway)
        uow = await request.get(UoW)
        product = await gateway.get(PRODUCT, for_update=True, eager_variants=True)
        assert product is not None
        variant = product.add_variant(_variant_data(), price=Money(amount=Decimal(8900)))
        await uow.commit()
    await _corrupt_overrides(
        engine,
        variant.id,
        overrides=[{"attribute_id": "not-a-uuid", "value_id": None, "quantity": "2"}],
    )

    async with container() as request:
        gateway = await request.get(ProductGateway)

        with pytest.raises(RuntimeError, match="corrupted variant overrides"):
            await gateway.get(PRODUCT, eager_variants=True)
