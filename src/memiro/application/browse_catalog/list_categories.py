from collections.abc import Sequence

from memiro.application.browse_catalog.models import CategoryModel
from memiro.application.common.gateway.catalog_read import CatalogReadGateway
from memiro_common.interactor import interactor


@interactor
class ListCategories:
    """List public catalogue categories."""

    catalog_read_gateway: CatalogReadGateway

    async def execute(self) -> Sequence[CategoryModel]:
        """Return visible categories."""
        return await self.catalog_read_gateway.list_categories()
