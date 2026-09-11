from memiro.application.browse_catalog.models import FIRST_PAGE, LandingsList
from memiro.application.browse_catalog.shared import photographed_tiles
from memiro.application.common.gateway.catalog_read import CatalogReadGateway
from memiro.application.common.gateway.product_image import ProductImageStorage
from memiro_common.interactor import interactor


@interactor
class ListLandings:
    """List the published landing pages of the storefront."""

    catalog_read_gateway: CatalogReadGateway
    image_storage: ProductImageStorage

    async def execute(self) -> LandingsList:
        """Return the landings the storefront shows as tiles."""
        landings, total = await self.catalog_read_gateway.list_landings()
        return LandingsList(items=await photographed_tiles(self.image_storage, landings), total=total, page=FIRST_PAGE)
