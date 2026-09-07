import structlog

from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.gateway.product_image import ProductImageStorage
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
    image_storage: ProductImageStorage

    async def execute(self, product_id: ProductId) -> None:
        """Remove one product, commit its transaction and drop the photo files nothing names any more."""
        logger.debug("Removing a product", product_id=product_id)
        # Nothing holds a product back: an inquiry keeps its own snapshot by
        # name, and the position survives the loss of the reference
        # (decision 9).
        product = await loaded_for_update(self.product_gateway, product_id, command="remove", eager_images=True)
        keys = [image.key for image in product.images]
        await self.uow.delete(product)
        await self.uow.commit()
        # After the commit, for the reason ``RemoveImage`` drops its file
        # after it: the rows are what the storefront reads, and files dropped
        # before them would leave a live gallery pointing at nothing.
        for key in keys:
            await self.image_storage.remove(key)
        logger.info("Product removed", product_id=product_id, images=len(keys))
