from decimal import Decimal

from dishka import AsyncContainer

from memiro.application.common.gateway.catalog import ProductGateway
from memiro.entities.catalog.product.entity import VariantData
from memiro.entities.common.identifiers import VariantId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro_common.uow import UoW
from tests.common.factory.catalog import PRODUCT


async def prime_variant(request: AsyncContainer) -> VariantId:
    """Arrange one child through the aggregate and its production gateway."""
    gateway: ProductGateway = await request.get(ProductGateway)
    uow = await request.get(UoW)
    product = await gateway.get(PRODUCT, for_update=True, eager_variants=True)
    assert product is not None
    variant = product.add_variant(
        VariantData(
            dimensions=Dimensions(
                width=Millimeters(value=800),
                height=Millimeters(value=600),
            ),
            overrides=(),
            sort_order=0,
        ),
        price=Money(amount=Decimal(8900)),
    )
    await uow.commit()
    return variant.id
