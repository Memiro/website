import structlog

from memiro.application.common.gateway.work import WorkGateway, WorkPhotoStorage
from memiro.application.errors.catalog import WorkNotFoundError
from memiro.entities.common.identifiers import WorkId
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


@interactor
class RemoveWork:
    """Interactor for taking one work out of the gallery."""

    uow: UoW
    work_gateway: WorkGateway
    photo_storage: WorkPhotoStorage

    async def execute(self, work_id: WorkId) -> None:
        """Take the work out, commit, and drop the file nothing names any more."""
        logger.debug("Removing a work", work_id=work_id)
        stored = await self.work_gateway.get(work_id)
        if stored is None:
            logger.warning("An unknown work was removed", work_id=work_id)
            raise WorkNotFoundError
        await self.work_gateway.remove(work_id)
        await self.uow.commit()
        # After the commit: the row is what the storefront reads, and a file
        # dropped before it would leave the gallery pointing at nothing.
        await self.photo_storage.remove(stored.photo_key)
        logger.info("Work removed", work_id=work_id, key=stored.photo_key)
