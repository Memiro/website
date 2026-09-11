from memiro.application.browse_catalog.models import ProductModel
from memiro.application.browse_catalog.shared import photographed
from memiro.application.common.gateway.catalog_read import CatalogReadGateway
from memiro.application.common.gateway.product_image import ProductImageStorage
from memiro.application.errors.catalog import ProductNotFoundError
from memiro_common.interactor import interactor


@interactor
class ReadProduct:
    """Read one published product card."""

    catalog_read_gateway: CatalogReadGateway
    image_storage: ProductImageStorage

    async def execute(self, slug: str) -> ProductModel:
        """Return the public card or hide its existence."""
        product = await self.catalog_read_gateway.read_product(slug)
        if product is None:
            raise ProductNotFoundError
        photographs = await photographed(self.image_storage, [product])
        return photographs[0]
