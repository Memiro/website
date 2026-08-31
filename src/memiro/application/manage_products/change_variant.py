import structlog

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.errors.catalog import ProductNotFoundError, VariantNotFoundError
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.application.manage_products.shared import VariantForm, variant_data, variant_price
from memiro.entities.common.identifiers import ProductId, VariantId
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class ChangeVariantForm(VariantForm):
    """Owner-controlled replacement of one existing variant."""


@interactor
class ChangeVariant:
    """Interactor for changing one precalculated product variant."""

    uow: UoW
    product_gateway: ProductGateway
    pricing_settings_gateway: PricingSettingsGateway
    attribute_gateway: AttributeGateway

    async def execute(
        self,
        product_id: ProductId,
        variant_id: VariantId,
        data: ChangeVariantForm,
    ) -> None:
        """Recalculate, replace and commit one product variant."""
        logger.debug("Changing a product variant", product_id=product_id, variant_id=variant_id)
        product = await self.product_gateway.get(product_id, for_update=True, eager_variants=True)
        if product is None:
            logger.warning("A variant was changed on an unknown product", product_id=product_id)
            raise ProductNotFoundError
        variant = product.variant(variant_id)
        if variant is None:
            logger.warning("An unknown product variant was changed", product_id=product_id, variant_id=variant_id)
            raise VariantNotFoundError
        settings = await self.pricing_settings_gateway.get_with_surcharges()
        if settings is None:
            logger.warning("A variant was changed before pricing setup", product_id=product_id)
            raise PricingSettingsNotFoundError
        attributes = await self.attribute_gateway.list_with_values()
        replacement = variant_data(data, product=product, attributes=attributes)
        price = variant_price(
            replacement,
            product=product,
            attributes=attributes,
            settings=settings,
        )
        product.change_variant(variant, replacement, price=price)
        await self.uow.commit()
        logger.info("Product variant changed", product_id=product_id, variant_id=variant_id)
