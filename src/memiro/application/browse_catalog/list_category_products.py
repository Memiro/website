from math import ceil

from memiro.application.browse_catalog.models import PAGE_SIZE, CatalogQuery, ProductsList
from memiro.application.common.gateway.catalog_read import CatalogReadGateway
from memiro.application.errors.catalog import CategoryNotFoundError
from memiro_common.interactor import interactor


@interactor
class ListCategoryProducts:
    """List public products within one category."""

    catalog_read_gateway: CatalogReadGateway

    async def execute(self, slug: str, query: CatalogQuery | None = None) -> ProductsList:
        """Return the page of public products the visitor narrowed the category to."""
        asked = query or CatalogQuery()
        if await self.catalog_read_gateway.read_category(slug) is None:
            raise CategoryNotFoundError
        products, total = await self.catalog_read_gateway.list_products_by_category(slug, asked)
        groups = await self.catalog_read_gateway.filter_groups(slug, asked)
        price = await self.catalog_read_gateway.price_bounds(slug, asked)
        return ProductsList(
            items=products,
            total=total,
            page=asked.page,
            pages=max(ceil(total / PAGE_SIZE), 1),
            groups=groups,
            price=price,
            sort=asked.sort,
        )
