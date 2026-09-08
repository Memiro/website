from memiro.application.browse_catalog.models import FIRST_PAGE, WorksList
from memiro.application.common.gateway.catalog_read import CatalogReadGateway
from memiro_common.interactor import interactor


@interactor
class ListWorks:
    """List the works the storefront's gallery is built from."""

    catalog_read_gateway: CatalogReadGateway

    async def execute(self) -> WorksList:
        """Return the published works in the owner's order."""
        works, total = await self.catalog_read_gateway.list_works()
        return WorksList(items=works, total=total, page=FIRST_PAGE)
