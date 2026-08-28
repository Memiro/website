import structlog
from pydantic import BaseModel, Field

from memiro.application.common.gateway.catalog import AttributeGateway, ProductGateway
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.common.input_limits import MAX_SIDE_MM, MIN_SIDE_MM
from memiro.application.errors.catalog import ProductNotFoundError, VariantNotFoundError
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.application.manage_products.shared import CreatedVariant, variant_price
from memiro.entities.catalog.product.entity import VariantData
from memiro.entities.common.identifiers import ProductId, VariantId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class DuplicateVariantWithSizeForm(BaseModel):
    """The new dimensions of a copied product variant."""

    width_mm: int = Field(ge=MIN_SIDE_MM, le=MAX_SIDE_MM)
    height_mm: int = Field(ge=MIN_SIDE_MM, le=MAX_SIDE_MM)


@interactor
class DuplicateVariantWithSize:
    """Interactor for copying one variant to another size."""

    uow: UoW
    product_gateway: ProductGateway
    pricing_settings_gateway: PricingSettingsGateway
    attribute_gateway: AttributeGateway

    async def execute(
        self,
        product_id: ProductId,
        variant_id: VariantId,
        data: DuplicateVariantWithSizeForm,
    ) -> CreatedVariant:
        """Recalculate, copy and commit one product variant."""
        logger.debug("Duplicating a product variant", product_id=product_id, variant_id=variant_id)
        product = await self.product_gateway.get(product_id, for_update=True, eager_variants=True)
        if product is None:
            logger.warning("A variant was duplicated on an unknown product", product_id=product_id)
            raise ProductNotFoundError
        variant = product.variant(variant_id)
        if variant is None:
            logger.warning("An unknown product variant was duplicated", product_id=product_id, variant_id=variant_id)
            raise VariantNotFoundError
        settings = await self.pricing_settings_gateway.get_with_surcharges()
        if settings is None:
            logger.warning("A variant was duplicated before pricing setup", product_id=product_id)
            raise PricingSettingsNotFoundError
        attributes = await self.attribute_gateway.list_with_values()
        duplicate_data = VariantData(
            dimensions=Dimensions(
                width=Millimeters(value=data.width_mm),
                height=Millimeters(value=data.height_mm),
            ),
            overrides=variant.overrides,
            sort_order=variant.sort_order,
        )
        price = variant_price(
            duplicate_data,
            product=product,
            attributes=attributes,
            settings=settings,
        )
        duplicate = product.duplicate_variant_with_size(
            variant,
            duplicate_data.dimensions,
            price=price,
        )
        await self.uow.commit()
        logger.info("Product variant duplicated", product_id=product_id, variant_id=duplicate.id)
        return CreatedVariant(id=duplicate.id)
