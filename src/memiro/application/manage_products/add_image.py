from pathlib import PurePosixPath

import structlog
from pydantic import BaseModel, Field, field_validator

from memiro.application.common.gateway.image_upload import ImageUpload
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.gateway.product_image import ProductImageStorage
from memiro.application.common.input_limits import IMAGE_EXTENSIONS, MAX_IMAGE_BYTES, MAX_NAME_LENGTH
from memiro.application.manage_products.shared import loaded_for_update
from memiro.entities.common.identifiers import ProductId
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class AddImageForm(BaseModel):
    """The photo the owner uploaded from the card of a product."""

    filename: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    content: bytes = Field(min_length=1, max_length=MAX_IMAGE_BYTES)

    @field_validator("filename")
    @classmethod
    def _a_photo_by_its_extension(cls, filename: str) -> str:
        """Take only what a browser shows as a photo: nothing here opens the file."""
        if PurePosixPath(filename).suffix.lstrip(".").lower() not in IMAGE_EXTENSIONS:
            msg = f"A product photo is one of {', '.join(IMAGE_EXTENSIONS)}"
            raise ValueError(msg)
        return filename


class CreatedProductImage(BaseModel):
    """The key the storage issued for the photo that was just stored."""

    key: str


@interactor
class AddImage:
    """Interactor for putting one photo into the gallery of a product."""

    uow: UoW
    product_gateway: ProductGateway
    image_storage: ProductImageStorage
    clock: Clock

    async def execute(self, product_id: ProductId, data: AddImageForm) -> CreatedProductImage:
        """Store one photo, name it in the gallery of the product and commit."""
        logger.debug("Adding a product photo", product_id=product_id)
        product = await loaded_for_update(self.product_gateway, product_id, command="add_image", eager_images=True)
        key = await self.image_storage.put(ImageUpload(filename=data.filename, content=data.content))
        if product.image(key) is not None:
            # The storage handed back a key a live row already names, so it has
            # just written over a photo of this very product. Dropping the file
            # now would take that photo with it: the storage is broken, and
            # this is a defect report, not an answer to the owner.
            msg = f"The image storage reissued a key product {product_id} already carries: {key}"
            raise RuntimeError(msg)
        try:
            product.add_image(key, clock=self.clock)
            await self.uow.commit()
        except Exception:
            # Nothing was stored, so nothing names the file: a photo the
            # database refused would stay on the volume for ever.
            await self.image_storage.remove(key)
            raise
        logger.info("Product photo added", product_id=product_id, key=key)
        return CreatedProductImage(key=key)
