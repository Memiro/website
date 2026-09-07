from memiro.application.browse_catalog.models import FIRST_PAGE, LandingsList
from memiro.application.common.gateway.catalog_read import CatalogReadGateway
from memiro_common.interactor import interactor


@interactor
class ListLandings:
    """List the published landing pages of the storefront."""

    catalog_read_gateway: CatalogReadGateway

    async def execute(self) -> LandingsList:
        """Return the landings the storefront shows as tiles."""
        landings, total = await self.catalog_read_gateway.list_landings()
        return LandingsList(items=landings, total=total, page=FIRST_PAGE)
