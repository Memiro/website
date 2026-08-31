from memiro.application.browse_catalog.models import FIRST_PAGE, ProductsList
from memiro.application.common.gateway.catalog_read import CatalogReadGateway
from memiro.application.errors.catalog import CategoryNotFoundError
from memiro_common.interactor import interactor


@interactor
class ListCategoryProducts:
    """List public products within one category."""

    catalog_read_gateway: CatalogReadGateway

    async def execute(self, slug: str) -> ProductsList:
        """Return public products of the category."""
        if await self.catalog_read_gateway.read_category(slug) is None:
            raise CategoryNotFoundError
        products, total = await self.catalog_read_gateway.list_products_by_category(slug)
        return ProductsList(items=products, total=total, page=FIRST_PAGE)
