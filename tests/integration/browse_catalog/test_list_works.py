import pytest
from dishka import AsyncContainer
from fastapi import FastAPI, status
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.adapters.storage.photo_files import DERIVATIVE_WIDTHS
from memiro.application.browse_catalog import WorkModel, WorkProduct, WorksList
from memiro.application.browse_catalog.models import ImageModel
from memiro.application.common.gateway.image_upload import ImageUpload
from memiro.application.common.gateway.work import WorkPhotoStorage
from tests.common.photograph import photograph
from tests.integration.api_client import ApiClient
from tests.integration.prime import prime_product_publication, prime_second_work, prime_work

pytestmark = pytest.mark.usefixtures("catalog")

# The fixture writes rows, not files, so the storage holds no copies of these
# photographs — the gallery draws them at the one size there is.
HALLWAY = WorkModel(
    photo_key="works/hallway.jpg",
    photo=ImageModel(key="works/hallway.jpg", variants=[]),
    title="Круглое зеркало в прихожей",
    description="Поставили в прихожей квартиры на Ленина.",
    product=WorkProduct(category_slug="mirrors", slug="zerkalo-v-rame"),
)


HALLWAY_WITHOUT_PRODUCT = WorkModel(
    photo_key="works/hallway.jpg",
    photo=ImageModel(key="works/hallway.jpg", variants=[]),
    title="Круглое зеркало в прихожей",
    description="Поставили в прихожей квартиры на Ленина.",
    product=None,
)


BATHROOM = WorkModel(
    photo_key="works/bathroom.jpg",
    photo=ImageModel(key="works/bathroom.jpg", variants=[]),
    title="Зеркало-капля в ванной",
    description="",
    product=None,
)


async def test_the_gallery_shows_the_installation_with_the_mirror_it_stands_on(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A published work reaches the gallery whole, the address of its mirror included."""
    await prime_work(engine)

    assert (await api_client.list_works()).assert_status(status.HTTP_200_OK).ensure_content() == WorksList(
        items=[HALLWAY], total=1, page=1
    )


async def test_a_gallery_the_owner_has_not_filled_yet_is_an_empty_envelope(api_client: ApiClient) -> None:
    """An empty gallery is a page of nothing, not a refusal."""
    assert (await api_client.list_works()).assert_status(status.HTTP_200_OK).ensure_content() == WorksList(
        items=[], total=0, page=1
    )


async def test_a_work_the_owner_has_not_published_stays_out_of_the_gallery(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A draft is the owner's own business: the gallery is what the storefront publishes."""
    await prime_work(engine, is_published=False)

    assert (await api_client.list_works()).assert_status(status.HTTP_200_OK).ensure_content() == WorksList(
        items=[], total=0, page=1
    )


async def test_the_gallery_keeps_the_order_the_owner_put_the_works_in(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """Works are shown in the owner's `sort_order`, not in the order they were entered."""
    await prime_work(engine, sort_order=2)
    await prime_second_work(engine, sort_order=1)

    assert (await api_client.list_works()).assert_status(status.HTTP_200_OK).ensure_content() == WorksList(
        items=[BATHROOM, HALLWAY], total=2, page=1
    )


async def test_a_work_that_names_no_mirror_is_a_photograph_and_nothing_more(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A work without a product carries no address: there is nothing to walk out to."""
    await prime_work(engine, product_id=None)

    assert (await api_client.list_works()).assert_status(status.HTTP_200_OK).ensure_content() == WorksList(
        items=[HALLWAY_WITHOUT_PRODUCT], total=1, page=1
    )


async def test_a_work_does_not_point_at_a_mirror_the_catalogue_stopped_selling(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """The storefront does not tell about the hidden: an unpublished product leaves the work an image."""
    await prime_work(engine)
    await prime_product_publication(engine, is_published=False)

    assert (await api_client.list_works()).assert_status(status.HTTP_200_OK).ensure_content() == WorksList(
        items=[HALLWAY_WITHOUT_PRODUCT], total=1, page=1
    )


async def test_a_photograph_of_the_gallery_carries_the_widths_it_was_made_at(
    api_client: ApiClient,
    app: FastAPI,
    engine: AsyncEngine,
) -> None:
    """The gallery is told which copies exist instead of spelling their addresses itself."""
    container: AsyncContainer = app.state.dishka_container
    storage = await container.get(WorkPhotoStorage)
    key = await storage.put(ImageUpload(filename="hallway.jpg", content=photograph()))
    await prime_work(engine, photo_key=key)

    gallery = (await api_client.list_works()).assert_status(status.HTTP_200_OK).ensure_content()

    photograph_of_the_work = gallery.items[0].photo
    assert photograph_of_the_work is not None
    assert [variant.width for variant in photograph_of_the_work.variants] == list(DERIVATIVE_WIDTHS)
