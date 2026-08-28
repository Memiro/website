from decimal import Decimal

import pytest
from dishka import AsyncContainer
from fastapi import FastAPI

from memiro.application.common.gateway.catalog import ProductGateway
from memiro.entities.catalog.product.entity import ConfiguredValue, DeclaredValue, VariantData
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
                configured=ConfiguredValue(value_id=SILVER, quantity=None),
            ),
            DeclaredValue(
                attribute_id=CUTOUTS,
                configured=ConfiguredValue(value_id=None, quantity=Decimal("2.50")),
            ),
        ),
        sort_order=3,
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
