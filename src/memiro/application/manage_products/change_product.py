import structlog

from memiro.application.common.gateway.category import CategoryGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.errors.catalog import CategoryNotFoundError
from memiro.application.manage_products.shared import (
    ProductForm,
    change_data,
    ensure_the_address_is_free,
    loaded_for_update,
)
from memiro.entities.catalog.product.entity import settled_slug
from memiro.entities.common.identifiers import ProductId
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class ChangeProductForm(ProductForm):
    """Owner-controlled root fields of the product being changed."""


@interactor
class ChangeProduct:
    """Interactor for restating the root of one product."""

    uow: UoW
    product_gateway: ProductGateway
    category_gateway: CategoryGateway
    clock: Clock

    async def execute(self, product_id: ProductId, data: ChangeProductForm) -> None:
        """Replace the root fields of one product and commit its transaction."""
        logger.debug("Changing a product", product_id=product_id)
        product = await loaded_for_update(self.product_gateway, product_id, command="change")
        if data.category_id != product.category_id and not await self.category_gateway.exists(data.category_id):
            logger.warning("A product was moved to an unknown section", category_id=data.category_id)
            raise CategoryNotFoundError
        restated = change_data(data)
        await ensure_the_address_is_free(
            self.product_gateway,
            settled_slug(restated.slug, restated.name),
            except_product=product_id,
        )
        product.change(restated, clock=self.clock)
        await self.uow.commit()
        logger.info("Product changed", product_id=product_id)
