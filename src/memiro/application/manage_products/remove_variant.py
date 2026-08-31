import structlog

from memiro.application.common.gateway.product import ProductGateway
from memiro.application.errors.catalog import ProductNotFoundError, VariantNotFoundError
from memiro.entities.common.identifiers import ProductId, VariantId
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


@interactor
class RemoveVariant:
    """Interactor for removing one precalculated product variant."""

    uow: UoW
    product_gateway: ProductGateway

    async def execute(self, product_id: ProductId, variant_id: VariantId) -> None:
        """Remove and commit one product variant."""
        logger.debug("Removing a product variant", product_id=product_id, variant_id=variant_id)
        product = await self.product_gateway.get(product_id, for_update=True, eager_variants=True)
        if product is None:
            logger.warning("A variant was removed from an unknown product", product_id=product_id)
            raise ProductNotFoundError
        variant = product.variant(variant_id)
        if variant is None:
            logger.warning("An unknown product variant was removed", product_id=product_id, variant_id=variant_id)
            raise VariantNotFoundError
        product.remove_variant(variant)
        await self.uow.commit()
        logger.info("Product variant removed", product_id=product_id, variant_id=variant_id)
