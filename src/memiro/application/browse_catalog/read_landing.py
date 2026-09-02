from memiro.application.browse_catalog.models import LandingModel
from memiro.application.common.gateway.catalog_read import CatalogReadGateway
from memiro.application.errors.catalog import LandingNotFoundError
from memiro_common.interactor import interactor


@interactor
class ReadLanding:
    """Read one published landing page by its public slug."""

    catalog_read_gateway: CatalogReadGateway

    async def execute(self, slug: str) -> LandingModel:
        """Return the landing, or refuse a slug the storefront does not publish."""
        landing = await self.catalog_read_gateway.read_landing(slug)
        if landing is None:
            raise LandingNotFoundError
        return landing
