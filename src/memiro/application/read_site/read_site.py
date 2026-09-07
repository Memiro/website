from memiro.application.common.gateway.site import SiteGateway
from memiro.application.read_site.models import SiteModel
from memiro_common.interactor import interactor


@interactor
class ReadSite:
    """Read the studio's contacts and the seller's requisites for the storefront."""

    site_gateway: SiteGateway

    async def execute(self) -> SiteModel:
        """Return what every page prints about the studio behind it."""
        return SiteModel(
            contacts=await self.site_gateway.read_contacts(),
            seller=await self.site_gateway.read_seller_requisites(),
        )
