from dataclasses import replace

import structlog

from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.gateway.work import WorkGateway, WorkPhotoStorage
from memiro.application.errors.catalog import WorkNotFoundError
from memiro.application.manage_works.shared import (
    PhotoForm,
    WorkCopyForm,
    ensure_the_product_is_in_the_catalogue,
    store_photo,
)
from memiro.entities.common.identifiers import WorkId
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class ChangeWorkForm(WorkCopyForm):
    """Owner-controlled fields of a saved work; an empty photo keeps the stored one."""

    photo: PhotoForm | None = None


@interactor
class ChangeWork:
    """Interactor for restating one work of the gallery, its photograph included."""

    uow: UoW
    work_gateway: WorkGateway
    product_gateway: ProductGateway
    photo_storage: WorkPhotoStorage

    async def execute(self, work_id: WorkId, data: ChangeWorkForm) -> None:
        """Restate the work whole, and let the photo it stood on go only once the new one is stored."""
        logger.debug("Restating a work", work_id=work_id)
        stored = await self.work_gateway.get(work_id)
        if stored is None:
            logger.warning("An unknown work was restated", work_id=work_id)
            raise WorkNotFoundError
        await ensure_the_product_is_in_the_catalogue(self.product_gateway, data.product_id)
        uploaded = None if data.photo is None else await store_photo(self.photo_storage, self.work_gateway, data.photo)
        try:
            await self.work_gateway.replace(
                replace(
                    stored,
                    photo_key=stored.photo_key if uploaded is None else uploaded,
                    product_id=data.product_id,
                    title=data.title,
                    description=data.description,
                    is_published=data.is_published,
                    sort_order=data.sort_order,
                ),
            )
            await self.uow.commit()
        except Exception:
            if uploaded is not None:
                await self.photo_storage.remove(uploaded)
            raise
        if uploaded is not None:
            # After the commit: the row is what the storefront reads, and a
            # file dropped before it would leave the gallery pointing at
            # nothing.
            await self.photo_storage.remove(stored.photo_key)
        logger.info("Work restated", work_id=work_id)
