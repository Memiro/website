import structlog

from memiro.application.common.gateway.product import ProductGateway
from memiro.application.manage_products.shared import loaded_for_update
from memiro.entities.common.identifiers import ProductId
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


@interactor
class RemoveProduct:
    """Interactor for removing one product with everything that belongs to it."""

    uow: UoW
    product_gateway: ProductGateway

    async def execute(self, product_id: ProductId) -> None:
        """Remove one product and commit its transaction."""
        logger.debug("Removing a product", product_id=product_id)
        # Nothing holds a product back: an inquiry keeps its own snapshot by
        # name, and the position survives the loss of the reference
        # (decision 9).
        product = await loaded_for_update(self.product_gateway, product_id, command="remove")
        await self.uow.delete(product)
        await self.uow.commit()
        logger.info("Product removed", product_id=product_id)
