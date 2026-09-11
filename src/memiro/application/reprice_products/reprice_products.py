from collections.abc import Sequence
from itertools import batched

import structlog
from pydantic import BaseModel

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


class RepricedCatalogue(BaseModel):
    """Count of the products a repricing moved."""

    product_count: int


@interactor
class RepriceProducts:
    """Interactor for recalculating every precalculated variant of the catalogue."""

    uow: UoW
    product_gateway: ProductGateway
    attribute_gateway: AttributeGateway
    pricing_settings_gateway: PricingSettingsGateway
    clock: Clock

    async def execute(self) -> RepricedCatalogue:
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
                if await self._repriced_any_variant(product_id, attributes, settings):
                    repriced += 1
            await self.uow.commit()
        logger.info("The catalogue was repriced", product_count=repriced)
        return RepricedCatalogue(product_count=repriced)

    async def _repriced_any_variant(
        self,
        product_id: ProductId,
        attributes: Sequence[Attribute],
        settings: PricingSettings,
    ) -> bool:
        """Reprice every variant of one product, and say whether any of them took a new price."""
        # The aggregate root is locked like any owner command locks it (§7.9):
        # a reprice and a hand edit of the same product must not overwrite
        # each other while the batch transaction is open.
        product = await self.product_gateway.get(product_id, for_update=True, eager_variants=True)
        if product is None:
            logger.warning("A product left the catalogue while it was being repriced", product_id=product_id)
            return False
        moved = False
        for variant in product.variants:
            if variant.price_is_manual:
                continue
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
            moved = True
        return moved


def _same_configuration(variant: Variant) -> VariantData:
    """Restate one variant as the command data of the aggregate, changing nothing but its price."""
    # Only variants the calculation prices reach here, so the restated data
    # carries no price of the owner's own (ADR-0017).
    return VariantData(
        dimensions=variant.dimensions,
        overrides=variant.overrides,
        sort_order=variant.sort_order,
    )
