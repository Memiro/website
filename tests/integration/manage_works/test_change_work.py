from uuid import uuid4

import pytest
from dishka import AsyncContainer
from sqlalchemy.exc import DBAPIError

from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.gateway.work import WorkGateway, WorkPhotoStorage
from memiro.application.errors.catalog import ProductNotFoundError, WorkNotFoundError
from memiro.application.manage_products import RemoveProduct
from memiro.application.manage_works import ChangeWork
from memiro.bootstrap.config_loader import Config
from memiro_common.uow import UoW
from tests.common.factory.catalog import PRODUCT
from tests.integration.manage_works.arrange import (
    PHOTO,
    SECOND_PHOTO,
    STORED_KEY_LENGTH,
    FakeWorkPhotoStorage,
    change_form,
    change_work,
    create_form,
    create_work,
    load_work,
    photo_form,
)

pytestmark = pytest.mark.usefixtures("catalog")


async def _with_storage(request: AsyncContainer, storage: WorkPhotoStorage) -> ChangeWork:
    """Build the production interactor over one fake: everything else comes from the app's own container."""
    return ChangeWork(
        uow=await request.get(UoW),
        work_gateway=await request.get(WorkGateway),
        product_gateway=await request.get(ProductGateway),
        photo_storage=storage,
    )


async def test_the_owner_restates_the_card_of_a_work(container: AsyncContainer) -> None:
    """The copy of a saved work is what the card says after the save."""
    created = await create_work(container, create_form())

    await change_work(container, created.id, change_form(title="Зеркало в ванной", is_published=False, sort_order=7))

    work = await load_work(container, created.id)
    assert work is not None
    assert (work.title, work.is_published, work.sort_order) == ("Зеркало в ванной", False, 7)


async def test_a_card_saved_without_a_photo_keeps_the_one_it_was_entered_with(
    container: AsyncContainer,
    config: Config,
) -> None:
    """An empty file field is not an erased photo: the work keeps the picture it stands on."""
    created = await create_work(container, create_form())
    entered = await load_work(container, created.id)
    assert entered is not None

    await change_work(container, created.id, change_form(title="Зеркало под другой подписью"))

    work = await load_work(container, created.id)
    assert work is not None
    assert work.photo_key == entered.photo_key
    assert (config.media.root / work.photo_key).read_bytes() == PHOTO


async def test_a_replaced_photo_leaves_the_storage_with_the_key_that_named_it(
    container: AsyncContainer,
    config: Config,
) -> None:
    """A photo nothing names any more is dropped: the row is what the storefront reads."""
    created = await create_work(container, create_form())
    entered = await load_work(container, created.id)
    assert entered is not None

    await change_work(container, created.id, change_form(photo=photo_form(content=SECOND_PHOTO)))

    work = await load_work(container, created.id)
    assert work is not None
    assert work.photo_key != entered.photo_key
    assert (config.media.root / work.photo_key).read_bytes() == SECOND_PHOTO
    assert not (config.media.root / entered.photo_key).exists()


async def test_a_work_lets_go_of_the_product_it_named(container: AsyncContainer) -> None:
    """The owner unlinks the mirror: the tile stays a photograph without a link."""
    created = await create_work(container, create_form())

    await change_work(container, created.id, change_form(product_id=None))

    work = await load_work(container, created.id)
    assert work is not None
    assert work.product_id is None


async def test_a_removed_product_leaves_the_work_where_it_stands(container: AsyncContainer) -> None:
    """A mirror the catalogue stopped selling takes its link, not the work: the link is set to nothing."""
    created = await create_work(container, create_form())

    async with container() as request:
        interactor = await request.get(RemoveProduct)
        await interactor.execute(PRODUCT)

    work = await load_work(container, created.id)
    assert work is not None
    assert work.product_id is None


async def test_a_card_of_a_work_nobody_entered_is_refused(container: AsyncContainer) -> None:
    """WORK_NOT_FOUND: there is no work behind this identifier."""
    with pytest.raises(WorkNotFoundError):
        await change_work(container, uuid4(), change_form())


async def test_a_link_to_an_unknown_product_is_refused(container: AsyncContainer) -> None:
    """PRODUCT_NOT_FOUND: a work names a mirror of this catalogue, not an identifier."""
    created = await create_work(container, create_form())

    with pytest.raises(ProductNotFoundError):
        await change_work(container, created.id, change_form(product_id=uuid4()))


async def test_a_photograph_the_database_refused_leaves_no_file_behind(
    container: AsyncContainer,
    config: Config,
) -> None:
    """A new photo no row ended up naming is dropped, and the work keeps the one it stood on."""
    created = await create_work(container, create_form())
    entered = await load_work(container, created.id)
    assert entered is not None
    # The interactor is composed here rather than overridden in the container:
    # only its storage is a fake, and the app's own container stays the one
    # every other test in this file talks to.
    storage = FakeWorkPhotoStorage(key=f"{'x' * (STORED_KEY_LENGTH + 1)}.jpg")

    async with container() as request:
        interactor = await _with_storage(request, storage)

        with pytest.raises(DBAPIError):
            await interactor.execute(created.id, change_form(photo=photo_form(content=SECOND_PHOTO)))

    assert storage.removed == [storage.key]
    work = await load_work(container, created.id)
    assert work is not None
    assert work.photo_key == entered.photo_key
    assert (config.media.root / entered.photo_key).read_bytes() == PHOTO


async def test_a_key_the_storage_reissued_never_takes_the_stored_photograph_with_it(
    container: AsyncContainer,
) -> None:
    """A key naming a photo the gallery already carries is a defect of the storage, not a refusal."""
    created = await create_work(container, create_form())
    entered = await load_work(container, created.id)
    assert entered is not None
    storage = FakeWorkPhotoStorage(key=entered.photo_key)

    async with container() as request:
        interactor = await _with_storage(request, storage)

        with pytest.raises(RuntimeError, match="reissued a key"):
            await interactor.execute(created.id, change_form(photo=photo_form(content=SECOND_PHOTO)))

    assert storage.removed == []
    work = await load_work(container, created.id)
    assert work is not None
    assert work.photo_key == entered.photo_key
