import structlog
from pydantic import BaseModel, Field

from memiro.application.common.gateway.category import CategoryGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.input_limits import MAX_DESCRIPTION_LENGTH
from memiro.application.errors.catalog import CategoryNotFoundError
from memiro.application.manage_products.shared import ProductForm, create_data, ensure_the_address_is_free
from memiro.entities.catalog.product.entity import product_factory, settled_slug
from memiro.entities.common.identifiers import ProductId
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class CreateProductForm(ProductForm):
    """Owner-controlled fields of the product being created."""

    # A blank card is the honest starting state of a product nobody has
    # written yet: no description, invisible on the storefront, no secret
    # about its price. A change has no such card and states all three.
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LENGTH)
    is_published: bool = False
    hides_calculated_price: bool = False


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
        entered = create_data(data)
        await ensure_the_address_is_free(
            self.product_gateway,
            settled_slug(entered.slug, entered.name),
            except_product=None,
        )
        product = product_factory(entered, clock=self.clock)
        self.uow.add(product)
        await self.uow.commit()
        logger.info("Product created", product_id=product.id)
        return CreatedProduct(id=product.id)
