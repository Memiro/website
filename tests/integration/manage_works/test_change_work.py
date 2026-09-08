from uuid import uuid4

import pytest
from dishka import AsyncContainer

from memiro.application.errors.catalog import ProductNotFoundError, WorkNotFoundError
from memiro.application.manage_products import RemoveProduct
from memiro.bootstrap.config_loader import Config
from tests.common.factory.catalog import PRODUCT
from tests.integration.manage_works.arrange import (
    PHOTO,
    SECOND_PHOTO,
    change_form,
    change_work,
    create_form,
    create_work,
    load_work,
    photo_form,
)

pytestmark = pytest.mark.usefixtures("catalog")


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
