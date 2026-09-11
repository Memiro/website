from memiro.application.browse_catalog.models import FIRST_PAGE, WorksList
from memiro.application.browse_catalog.shared import photographed_works
from memiro.application.common.gateway.catalog_read import CatalogReadGateway
from memiro.application.common.gateway.work import WorkPhotoStorage
from memiro_common.interactor import interactor


@interactor
class ListWorks:
    """List the works the storefront's gallery is built from."""

    catalog_read_gateway: CatalogReadGateway
    photo_storage: WorkPhotoStorage

    async def execute(self) -> WorksList:
        """Return the published works in the owner's order."""
        works, total = await self.catalog_read_gateway.list_works()
        return WorksList(items=await photographed_works(self.photo_storage, works), total=total, page=FIRST_PAGE)
