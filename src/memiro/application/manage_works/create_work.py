from uuid import uuid4

import structlog
from pydantic import BaseModel

from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.gateway.work import WorkGateway, WorkPhotoStorage, WorkRow
from memiro.application.manage_works.shared import (
    PhotoForm,
    WorkCopyForm,
    ensure_the_product_is_in_the_catalogue,
    stored_photo,
)
from memiro.entities.common.identifiers import WorkId
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class CreateWorkForm(WorkCopyForm):
    """Owner-controlled fields of the work being entered, its photo included."""

    photo: PhotoForm


class CreatedWork(BaseModel):
    """Identifier of a newly entered work."""

    id: WorkId


@interactor
class CreateWork:
    """Interactor for entering one installed mirror into the gallery of works."""

    uow: UoW
    work_gateway: WorkGateway
    product_gateway: ProductGateway
    photo_storage: WorkPhotoStorage

    async def execute(self, data: CreateWorkForm) -> CreatedWork:
        """Store the photo, name it by a work of the gallery and commit."""
        logger.debug("Entering a work", product_id=data.product_id)
        await ensure_the_product_is_in_the_catalogue(self.product_gateway, data.product_id)
        key = await stored_photo(self.photo_storage, self.work_gateway, data.photo)
        work = WorkRow(
            id=uuid4(),
            photo_key=key,
            product_id=data.product_id,
            title=data.title,
            description=data.description,
            is_published=data.is_published,
            sort_order=data.sort_order,
        )
        try:
            await self.work_gateway.add(work)
            await self.uow.commit()
        except Exception:
            # Nothing was stored, so nothing names the file: a photo the
            # database refused would stay on the volume for ever.
            await self.photo_storage.remove(key)
            raise
        logger.info("Work entered", work_id=work.id, key=key)
        return CreatedWork(id=work.id)
