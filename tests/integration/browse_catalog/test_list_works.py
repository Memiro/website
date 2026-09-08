import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.browse_catalog import WorkModel, WorkProduct, WorksList
from tests.integration.api_client import ApiClient
from tests.integration.prime import prime_product_publication, prime_second_work, prime_work

pytestmark = pytest.mark.usefixtures("catalog")

HALLWAY = WorkModel(
    photo_key="works/hallway.jpg",
    title="Круглое зеркало в прихожей",
    description="Поставили в прихожей квартиры на Ленина.",
    product=WorkProduct(category_slug="mirrors", slug="zerkalo-v-rame"),
)


BATHROOM = WorkModel(
    photo_key="works/bathroom.jpg",
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

    works = (await api_client.list_works()).assert_status(status.HTTP_200_OK).ensure_content()

    assert works.items == [HALLWAY.model_copy(update={"product": None})]


async def test_a_work_does_not_point_at_a_mirror_the_catalogue_stopped_selling(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """The storefront does not tell about the hidden: an unpublished product leaves the work an image."""
    await prime_work(engine)
    await prime_product_publication(engine, is_published=False)

    works = (await api_client.list_works()).assert_status(status.HTTP_200_OK).ensure_content()

    assert works.items == [HALLWAY.model_copy(update={"product": None})]
