from collections.abc import Sequence

from memiro.application.browse_catalog.models import ProductSummary
from memiro.application.common.gateway.catalog_read import CatalogReadGateway
from memiro.application.errors.catalog import CategoryNotFoundError
from memiro_common.interactor import interactor


@interactor
class ListCategoryProducts:
    """List public products within one category."""

    catalog_read_gateway: CatalogReadGateway

    async def execute(self, slug: str) -> Sequence[ProductSummary]:
        """Return public products of the category."""
        found, products = await self.catalog_read_gateway.list_products(slug)
        if not found:
            raise CategoryNotFoundError
        return products
