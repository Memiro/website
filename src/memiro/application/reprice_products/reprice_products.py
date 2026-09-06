from collections.abc import Sequence
from itertools import batched

import structlog

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.variant_pricing import variant_price
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.catalog.product.entity import Variant, VariantData
from memiro.entities.common.identifiers import ProductId
from memiro.entities.pricing.pricing_settings import PricingSettings
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

# The owner fixed the ceiling at 100-300 products (ADR-0014): a transaction per
# fifty keeps each one short without buying an optimization nobody needs.
PRODUCTS_PER_TRANSACTION = 50

logger: Logger = structlog.get_logger(__name__)


@interactor
class RepriceProducts:
    """Interactor for recalculating every precalculated variant of the catalogue."""

    uow: UoW
    product_gateway: ProductGateway
    attribute_gateway: AttributeGateway
    pricing_settings_gateway: PricingSettingsGateway
    clock: Clock

    async def execute(self) -> int:
        """Reprice the catalogue in batches and say how many products it moved."""
        logger.debug("Repricing the catalogue")
        settings = await self.pricing_settings_gateway.get_with_surcharges()
        if settings is None:
            logger.warning("The catalogue was repriced before pricing setup")
            raise PricingSettingsNotFoundError
        attributes = await self.attribute_gateway.list_with_values()
        repriced = 0
        for batch in batched(await self.product_gateway.all_ids(), PRODUCTS_PER_TRANSACTION, strict=False):
            for product_id in batch:
                repriced += await self._moved_any_price(product_id, attributes, settings)
            await self.uow.commit()
        logger.info("The catalogue was repriced", product_count=repriced)
        return repriced

    async def _moved_any_price(
        self,
        product_id: ProductId,
        attributes: Sequence[Attribute],
        settings: PricingSettings,
    ) -> int:
        """Reprice every variant of one product, and count the product when any of them took a new price."""
        product = await self.product_gateway.get(product_id, eager_variants=True)
        if product is None:
            logger.warning("A product left the catalogue while it was being repriced", product_id=product_id)
            return 0
        moved = 0
        for variant in product.variants:
            configuration = _same_configuration(variant)
            price = variant_price(configuration, product=product, attributes=attributes, settings=settings)
            if price is None:
                logger.warning(
                    "A variant is no longer priceable and keeps the price it had",
                    product_id=product.id,
                    variant_id=variant.id,
                )
                continue
            product.change_variant(variant, configuration, price=price, clock=self.clock)
            moved += 1
        return min(moved, 1)


def _same_configuration(variant: Variant) -> VariantData:
    """Restate one variant as the command data of the aggregate, changing nothing but its price."""
    return VariantData(
        dimensions=variant.dimensions,
        overrides=variant.overrides,
        sort_order=variant.sort_order,
    )
