import structlog

from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.gateway.product_image import ProductImageStorage
from memiro.application.errors.catalog import ProductImageNotFoundError
from memiro.application.manage_products.shared import loaded_for_update
from memiro.entities.common.identifiers import ProductId
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


@interactor
class RemoveImage:
    """Interactor for taking one photo out of the gallery of a product."""

    uow: UoW
    product_gateway: ProductGateway
    image_storage: ProductImageStorage
    clock: Clock

    async def execute(self, product_id: ProductId, key: str) -> None:
        """Take one photo out of the gallery, commit, and drop the file nothing names any more."""
        logger.debug("Removing a product photo", product_id=product_id, key=key)
        product = await loaded_for_update(self.product_gateway, product_id, command="remove_image", eager_images=True)
        image = product.image(key)
        if image is None:
            logger.warning("An unknown product photo was removed", product_id=product_id, key=key)
            raise ProductImageNotFoundError
        product.remove_image(image, clock=self.clock)
        await self.uow.commit()
        # After the commit: the row is what the storefront reads, and a file
        # dropped before it would leave the gallery pointing at nothing.
        await self.image_storage.remove(key)
        logger.info("Product photo removed", product_id=product_id, key=key)
