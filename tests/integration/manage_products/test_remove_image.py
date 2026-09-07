from uuid import uuid4

import pytest
from dishka import AsyncContainer

from memiro.application.errors.catalog import ProductImageNotFoundError, ProductNotFoundError
from memiro.application.manage_products import AddedImage, AddImage, AddImageForm, RemoveImage
from memiro.bootstrap.config_loader import Config
from memiro.entities.common.identifiers import ProductId
from tests.common.factory.catalog import PRODUCT
from tests.integration.manage_products.arrange import load_product

pytestmark = pytest.mark.usefixtures("catalog")

PHOTO = b"\xff\xd8\xff\xd9"


async def _add(container: AsyncContainer) -> AddedImage:
    """Put one photo on the canonical product to take off again."""
    async with container() as request:
        interactor = await request.get(AddImage)
        return await interactor.execute(PRODUCT, AddImageForm(filename="mirror.jpg", content=PHOTO))


async def _remove(container: AsyncContainer, product_id: ProductId, key: str) -> None:
    """Execute one removal in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(RemoveImage)
        await interactor.execute(product_id, key)


async def test_the_owner_takes_a_photo_off_the_product_card(container: AsyncContainer, config: Config) -> None:
    """A photo the owner removed leaves both the gallery and the storage."""
    added = await _add(container)

    await _remove(container, PRODUCT, added.key)

    product = await load_product(container, PRODUCT)
    assert product is not None
    assert product.images == ()
    assert not (config.media.root / added.key).exists()


async def test_a_photo_no_product_holds_is_refused(container: AsyncContainer) -> None:
    """A key the product does not carry names nothing: PRODUCT_IMAGE_NOT_FOUND."""
    await _add(container)

    with pytest.raises(ProductImageNotFoundError):
        await _remove(container, PRODUCT, "nobody.jpg")


async def test_a_photo_of_an_unknown_product_is_refused(container: AsyncContainer) -> None:
    """A gallery needs a product to belong to: PRODUCT_NOT_FOUND."""
    with pytest.raises(ProductNotFoundError):
        await _remove(container, uuid4(), "nobody.jpg")
