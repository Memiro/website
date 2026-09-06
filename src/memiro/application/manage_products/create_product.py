import structlog
from pydantic import BaseModel

from memiro.application.common.gateway.category import CategoryGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.errors.catalog import CategoryNotFoundError
from memiro.application.manage_products.shared import ProductForm, ensure_the_address_is_free, product_data
from memiro.entities.catalog.product.entity import product_factory
from memiro.entities.common.identifiers import ProductId
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class CreateProductForm(ProductForm):
    """Owner-controlled fields of the product being created."""


class CreatedProduct(BaseModel):
    """Identifier of a newly created product."""

    id: ProductId


@interactor
class CreateProduct:
    """Interactor for entering one product into a section of the catalogue."""

    uow: UoW
    category_gateway: CategoryGateway
    product_gateway: ProductGateway
    clock: Clock

    async def execute(self, data: CreateProductForm) -> CreatedProduct:
        """Create one product and commit its transaction."""
        logger.debug("Creating a product", category_id=data.category_id)
        if not await self.category_gateway.exists(data.category_id):
            logger.warning("A product was created in an unknown section", category_id=data.category_id)
            raise CategoryNotFoundError
        # The address is settled by the aggregate before it is asked about:
        # a product entered without one answers on the address of its name.
        product = product_factory(product_data(data), clock=self.clock)
        await ensure_the_address_is_free(self.product_gateway, product.slug, owner=None)
        self.uow.add(product)
        await self.uow.commit()
        logger.info("Product created", product_id=product.id)
        return CreatedProduct(id=product.id)
