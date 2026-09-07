import structlog

from memiro.application.common.gateway.landing import LandingGateway
from memiro.application.manage_landings.shared import loaded_for_update
from memiro.entities.common.identifiers import LandingId
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


@interactor
class RemoveLanding:
    """Interactor for removing one landing page with the narrowing that belongs to it."""

    uow: UoW
    landing_gateway: LandingGateway

    async def execute(self, landing_id: LandingId) -> None:
        """Remove one landing and commit its transaction; nothing in the catalogue holds it back."""
        logger.debug("Removing a landing", landing_id=landing_id)
        landing = await loaded_for_update(self.landing_gateway, landing_id, command="remove")
        await self.uow.delete(landing)
        await self.uow.commit()
        logger.info("Landing removed", landing_id=landing_id)
