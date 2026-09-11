from math import ceil

from memiro.application.browse_catalog.models import PAGE_SIZE, CatalogQuery, ProductsList
from memiro.application.browse_catalog.shared import photographed
from memiro.application.common.gateway.catalog_read import CatalogReadGateway
from memiro.application.common.gateway.product_image import ProductImageStorage
from memiro.application.errors.catalog import CategoryNotFoundError
from memiro_common.interactor import interactor


@interactor
class ListCategoryProducts:
    """List public products within one category."""

    catalog_read_gateway: CatalogReadGateway
    image_storage: ProductImageStorage

    async def execute(self, slug: str, query: CatalogQuery) -> ProductsList:
        """Return the page of public products the visitor narrowed the category to."""
        if await self.catalog_read_gateway.read_category(slug) is None:
            raise CategoryNotFoundError
        products, total = await self.catalog_read_gateway.list_products_by_category(slug, query)
        groups = await self.catalog_read_gateway.filter_groups(slug, query)
        price = await self.catalog_read_gateway.price_bounds(slug, query)
        return ProductsList(
            items=await photographed(self.image_storage, products),
            total=total,
            page=query.page,
            pages=max(ceil(total / PAGE_SIZE), 1),
            groups=groups,
            price=price,
            sort=query.sort,
        )
