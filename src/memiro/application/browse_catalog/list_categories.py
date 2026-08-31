from memiro.application.browse_catalog.models import FIRST_PAGE, CategoriesList
from memiro.application.common.gateway.catalog_read import CatalogReadGateway
from memiro_common.interactor import interactor


@interactor
class ListCategories:
    """List public catalogue categories."""

    catalog_read_gateway: CatalogReadGateway

    async def execute(self) -> CategoriesList:
        """Return visible categories."""
        categories, total = await self.catalog_read_gateway.list_categories()
        return CategoriesList(items=categories, total=total, page=FIRST_PAGE)
