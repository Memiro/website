from decimal import Decimal

import structlog
from pydantic import BaseModel

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.variant_pricing import settled_variant_price
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.application.manage_products.shared import VariantForm, loaded_for_reading, variant_data
from memiro.entities.common.identifiers import ProductId
from memiro_common.interactor import interactor
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)


class QuoteVariantForm(VariantForm):
    """Owner-controlled fields of the variant being priced before it is written."""


class QuotedVariant(BaseModel):
    """The price the assembled variant would be saved with."""

    price: Decimal


@interactor
class QuoteVariant:
    """Interactor for pricing one assembled variant without writing it."""

    product_gateway: ProductGateway
    pricing_settings_gateway: PricingSettingsGateway
    attribute_gateway: AttributeGateway

    async def execute(self, product_id: ProductId, data: QuoteVariantForm) -> QuotedVariant:
        """Price one assembled variant by the very function that would save it."""
        logger.debug("Quoting a product variant", product_id=product_id)
        product = await loaded_for_reading(self.product_gateway, product_id, command="quote_variant")
        settings = await self.pricing_settings_gateway.get_with_surcharges()
        if settings is None:
            logger.warning("A variant was quoted before pricing setup", product_id=product_id)
            raise PricingSettingsNotFoundError
        attributes = await self.attribute_gateway.list_with_values()
        variant = variant_data(data, product=product, attributes=attributes)
        price = settled_variant_price(
            variant,
            product=product,
            attributes=attributes,
            settings=settings,
        )
        return QuotedVariant(price=price.amount)
