"""What the three work scenarios share: the card of a work and the file on it."""

from pathlib import PurePosixPath

from pydantic import BaseModel, Field, field_validator

from memiro.application.common.gateway.image_upload import ImageUpload
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.gateway.work import WorkGateway, WorkPhotoStorage
from memiro.application.common.input_limits import (
    IMAGE_EXTENSIONS,
    MAX_DESCRIPTION_LENGTH,
    MAX_IMAGE_BYTES,
    MAX_NAME_LENGTH,
    MIN_NAME_LENGTH,
)
from memiro.application.errors.catalog import ProductNotFoundError
from memiro.entities.common.identifiers import ProductId


class PhotoForm(BaseModel):
    """The photo the owner uploaded from the card of a work."""

    filename: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    content: bytes = Field(min_length=1, max_length=MAX_IMAGE_BYTES)

    @field_validator("filename")
    @classmethod
    def _a_photo_by_its_extension(cls, filename: str) -> str:
        """Take only what a browser shows as a photo: nothing here opens the file."""
        if PurePosixPath(filename).suffix.lstrip(".").lower() not in IMAGE_EXTENSIONS:
            msg = f"A work photo is one of {', '.join(IMAGE_EXTENSIONS)}"
            raise ValueError(msg)
        return filename


class WorkCopyForm(BaseModel):
    """Owner-controlled fields of a work, its photo apart."""

    product_id: ProductId | None = None
    title: str = Field(min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH)
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LENGTH)
    is_published: bool
    sort_order: int = Field(ge=0)


async def ensure_the_product_is_in_the_catalogue(gateway: ProductGateway, product_id: ProductId | None) -> None:
    """Refuse a work that names a mirror this catalogue never sold; naming none is not a refusal."""
    if product_id is not None and not await gateway.exists(product_id):
        raise ProductNotFoundError


async def store_photo(storage: WorkPhotoStorage, gateway: WorkGateway, photo: PhotoForm) -> str:
    """Write the file to the storage and answer with the key the row will carry."""
    key = await storage.put(ImageUpload(filename=photo.filename, content=photo.content))
    if await gateway.holds_photo(key):
        # The storage handed back a key a live row already names, so it has
        # just written over the photo of another work. Dropping the file now
        # would take that photo with it: the storage is broken, and this is a
        # defect report, not an answer to the owner.
        msg = f"The work photo storage reissued a key the gallery already carries: {key}"
        raise RuntimeError(msg)
    return key
