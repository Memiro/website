import structlog

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.errors.catalog import ProductNotFoundError
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.application.manage_products.shared import CreatedVariant, VariantForm, variant_data, variant_price
from memiro.entities.common.identifiers import ProductId
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class AddVariantForm(VariantForm):
    """Owner-controlled fields of the variant being added."""


@interactor
class AddVariant:
    """Interactor for adding one precalculated variant to a product."""

    uow: UoW
    product_gateway: ProductGateway
    pricing_settings_gateway: PricingSettingsGateway
    attribute_gateway: AttributeGateway
    clock: Clock

    async def execute(self, product_id: ProductId, data: AddVariantForm) -> CreatedVariant:
        """Calculate, add and commit one product variant."""
        logger.debug("Adding a product variant", product_id=product_id)
        product = await self.product_gateway.get(product_id, for_update=True, eager_variants=True)
        if product is None:
            logger.warning("A variant was added to an unknown product", product_id=product_id)
            raise ProductNotFoundError
        settings = await self.pricing_settings_gateway.get_with_surcharges()
        if settings is None:
            logger.warning("A variant was added before pricing setup", product_id=product_id)
            raise PricingSettingsNotFoundError
        attributes = await self.attribute_gateway.list_with_values()
        variant = variant_data(data, product=product, attributes=attributes)
        price = variant_price(
            variant,
            product=product,
            attributes=attributes,
            settings=settings,
        )
        created = product.add_variant(variant, price=price, clock=self.clock)
        await self.uow.commit()
        logger.info("Product variant added", product_id=product_id, variant_id=created.id)
        return CreatedVariant(id=created.id)
