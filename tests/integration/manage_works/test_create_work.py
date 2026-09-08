from pathlib import Path
from uuid import uuid4

import pytest
from dishka import AsyncContainer
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError

from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.gateway.work import WorkGateway, WorkPhotoStorage
from memiro.application.common.input_limits import MAX_IMAGE_BYTES, MAX_NAME_LENGTH
from memiro.application.errors.catalog import ProductNotFoundError
from memiro.application.manage_works import CreatedWork, CreateWork
from memiro.bootstrap.config_loader import Config
from memiro_common.uow import UoW
from tests.common.factory.catalog import PRODUCT
from tests.integration.manage_works.arrange import (
    PHOTO,
    STORED_KEY_LENGTH,
    WORK_TITLE,
    FakeWorkPhotoStorage,
    create_form,
    create_work,
    load_work,
    photo_form,
)

pytestmark = pytest.mark.usefixtures("catalog")


async def _with_storage(request: AsyncContainer, storage: WorkPhotoStorage) -> CreateWork:
    """Build the production interactor over one fake: everything else comes from the app's own container."""
    return CreateWork(
        uow=await request.get(UoW),
        work_gateway=await request.get(WorkGateway),
        product_gateway=await request.get(ProductGateway),
        photo_storage=storage,
    )


async def test_the_owner_enters_a_work_into_the_gallery(container: AsyncContainer, config: Config) -> None:
    """A new work is stored with the copy of the card, and its photo goes to the storage."""
    created: CreatedWork = await create_work(container, create_form())

    work = await load_work(container, created.id)

    assert work is not None
    assert (work.title, work.product_id, work.is_published, work.sort_order) == (WORK_TITLE, PRODUCT, True, 1)
    assert (config.media.root / work.photo_key).read_bytes() == PHOTO


async def test_a_stored_work_is_named_by_a_key_the_storage_issued(container: AsyncContainer) -> None:
    """The database carries a key, not the name of the file the owner picked."""
    created = await create_work(container, create_form())

    work = await load_work(container, created.id)

    assert work is not None
    assert work.photo_key != "installed.JPG"
    assert Path(work.photo_key).suffix == ".jpg"


async def test_a_work_stands_in_the_gallery_without_a_product(container: AsyncContainer) -> None:
    """A photo of an installation the catalogue no longer sells is still a work."""
    created = await create_work(container, create_form(product_id=None))

    work = await load_work(container, created.id)

    assert work is not None
    assert work.product_id is None


async def test_a_work_of_an_unknown_product_is_refused(container: AsyncContainer) -> None:
    """PRODUCT_NOT_FOUND: a work names a mirror of this catalogue, not an identifier."""
    with pytest.raises(ProductNotFoundError):
        await create_work(container, create_form(product_id=uuid4()))


async def test_a_file_that_is_not_a_photo_is_refused_by_the_form() -> None:
    """The card takes photos, and the extension is what says so."""
    with pytest.raises(ValidationError):
        create_form(photo=photo_form(filename="prices.pdf"))


async def test_a_file_larger_than_the_limit_is_refused_by_the_form() -> None:
    """One photo above the input bound is not an upload the card accepts."""
    with pytest.raises(ValidationError):
        create_form(photo=photo_form(content=b"\x00" * (MAX_IMAGE_BYTES + 1)))


async def test_a_name_longer_than_the_limit_is_refused_by_the_form() -> None:
    """A file name is bounded by the column the key it becomes is stored in."""
    with pytest.raises(ValidationError):
        create_form(photo=photo_form(filename=f"{'a' * MAX_NAME_LENGTH}.jpg"))


async def test_a_title_nobody_typed_is_refused_by_the_form() -> None:
    """The title is the caption of the tile and the alt of the picture: a work without one is not a work."""
    with pytest.raises(ValidationError):
        create_form(title="")


async def test_a_work_the_database_refused_leaves_no_file_behind(container: AsyncContainer) -> None:
    """A photo no row ended up naming is dropped from the storage: nobody else knows its key."""
    # The interactor is composed here rather than overridden in the container:
    # only its storage is a fake, and the app's own container stays the one
    # every other test in this file talks to.
    storage = FakeWorkPhotoStorage(key=f"{'x' * (STORED_KEY_LENGTH + 1)}.jpg")
    async with container() as request:
        interactor = await _with_storage(request, storage)

        with pytest.raises(DBAPIError):
            await interactor.execute(create_form())

    assert storage.removed == [storage.key]


async def test_a_key_the_storage_reissued_never_takes_the_stored_photo_with_it(container: AsyncContainer) -> None:
    """A key naming a photo another work already carries is a defect of the storage, not a refusal."""
    storage = FakeWorkPhotoStorage(key="reissued.jpg")
    async with container() as request:
        interactor = await _with_storage(request, storage)
        await interactor.execute(create_form())

        with pytest.raises(RuntimeError, match="reissued a key"):
            await interactor.execute(create_form())

    assert storage.removed == []
