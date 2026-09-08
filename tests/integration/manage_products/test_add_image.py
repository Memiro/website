from pathlib import Path
from typing import override
from uuid import uuid4

import pytest
from dishka import AsyncContainer
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError

from memiro.application.common.gateway.image_upload import ImageUpload
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.gateway.product_image import ProductImageStorage
from memiro.application.common.input_limits import MAX_IMAGE_BYTES, MAX_NAME_LENGTH
from memiro.application.errors.catalog import ProductNotFoundError
from memiro.application.manage_products import AddImage, AddImageForm, CreatedProductImage
from memiro.bootstrap.config_loader import Config
from memiro.entities.common.identifiers import ProductId
from memiro_common.clock import Clock
from memiro_common.uow import UoW
from tests.common.factory.catalog import PRODUCT
from tests.integration.manage_products.arrange import load_product

pytestmark = pytest.mark.usefixtures("catalog")

# The smallest file that is still a file: what these tests upload is a photo
# only by its name, and nothing in the slice looks inside it.
PHOTO = b"\xff\xd8\xff\xd9"

# The owner uploads one photo; the second one of the same gallery follows it.
SECOND_PLACE = 1

# The column the issued key is stored in: a longer one is what the database
# refuses after the file has already been written.
STORED_KEY_LENGTH = 255


class FakeProductImageStorage(ProductImageStorage):
    """Storage that issues one key over and over and remembers what was dropped."""

    def __init__(self, key: str) -> None:
        """Keep the one key this storage answers with and the log of removals."""
        self.key = key
        self.removed: list[str] = []

    @override
    async def put(self, upload: ImageUpload) -> str:
        """Answer with the key this storage was built around."""
        return self.key

    @override
    async def remove(self, key: str) -> None:
        """Remember which key the caller dropped."""
        self.removed.append(key)


def _form(**overrides: object) -> AddImageForm:
    """Build the upload the owner sends from the card of a product."""
    fields: dict[str, object] = {"filename": "mirror.JPG", "content": PHOTO}
    return AddImageForm.model_validate(fields | overrides)


async def _with_storage(request: AsyncContainer, storage: ProductImageStorage) -> AddImage:
    """Build the production interactor over one fake: everything else comes from the app's own container."""
    return AddImage(
        uow=await request.get(UoW),
        product_gateway=await request.get(ProductGateway),
        image_storage=storage,
        clock=await request.get(Clock),
    )


async def _add(container: AsyncContainer, product_id: ProductId, form: AddImageForm) -> CreatedProductImage:
    """Execute one upload in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(AddImage)
        return await interactor.execute(product_id, form)


async def test_the_owner_puts_a_photo_on_the_product_card(container: AsyncContainer, config: Config) -> None:
    """An uploaded photo is stored on the storage and named by the gallery of the product."""
    added = await _add(container, PRODUCT, _form())

    product = await load_product(container, PRODUCT)
    assert product is not None
    assert [image.key for image in product.images] == [added.key]
    assert (config.media.root / added.key).read_bytes() == PHOTO


async def test_a_stored_photo_is_named_by_a_key_the_storage_issued(container: AsyncContainer) -> None:
    """The database carries a key, not the name of the file the owner picked."""
    added = await _add(container, PRODUCT, _form())

    assert added.key != "mirror.JPG"
    assert Path(added.key).suffix == ".jpg"


async def test_a_second_photo_stands_behind_the_first(container: AsyncContainer) -> None:
    """A gallery keeps the order the owner uploaded it in."""
    await _add(container, PRODUCT, _form())

    second = await _add(container, PRODUCT, _form(filename="mirror-side.jpg"))

    product = await load_product(container, PRODUCT)
    assert product is not None
    assert product.image(second.key) is not None
    assert product.image(second.key).sort_order == SECOND_PLACE  # type: ignore[union-attr]  # asserted above


async def test_a_photo_of_an_unknown_product_is_refused(container: AsyncContainer) -> None:
    """A photo needs a product to belong to: PRODUCT_NOT_FOUND."""
    with pytest.raises(ProductNotFoundError):
        await _add(container, uuid4(), _form())


async def test_a_file_that_is_not_a_photo_is_refused_by_the_form() -> None:
    """The card takes photos, and the extension is what says so."""
    with pytest.raises(ValidationError):
        _form(filename="prices.pdf")


async def test_a_file_larger_than_the_limit_is_refused_by_the_form() -> None:
    """One photo above the input bound is not an upload the card accepts."""
    with pytest.raises(ValidationError):
        _form(content=b"\x00" * (MAX_IMAGE_BYTES + 1))


async def test_a_name_longer_than_the_limit_is_refused_by_the_form() -> None:
    """A file name is bounded by the column the key it becomes is stored in."""
    with pytest.raises(ValidationError):
        _form(filename=f"{'a' * MAX_NAME_LENGTH}.jpg")


async def test_a_photo_the_database_refused_leaves_no_file_behind(container: AsyncContainer) -> None:
    """A photo no row ended up naming is dropped from the storage: nobody else knows its key."""
    # The interactor is composed here rather than overridden in the container:
    # only its storage is a fake, and the app's own container stays the one
    # every other test in this file talks to.
    storage = FakeProductImageStorage(key=f"{'x' * (STORED_KEY_LENGTH + 1)}.jpg")
    async with container() as request:
        interactor = await _with_storage(request, storage)

        with pytest.raises(DBAPIError):
            await interactor.execute(PRODUCT, _form())

    assert storage.removed == [storage.key]


async def test_a_key_the_storage_reissued_never_takes_the_stored_photo_with_it(
    container: AsyncContainer,
) -> None:
    """A key naming a photo the product already carries is a defect of the storage, not a refusal."""
    storage = FakeProductImageStorage(key="reissued.jpg")
    async with container() as request:
        interactor = await _with_storage(request, storage)
        await interactor.execute(PRODUCT, _form())

        with pytest.raises(RuntimeError, match="reissued a key"):
            await interactor.execute(PRODUCT, _form())

    assert storage.removed == []
    product = await load_product(container, PRODUCT)
    assert product is not None
    assert [image.key for image in product.images] == ["reissued.jpg"]
