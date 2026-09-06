from uuid import uuid4

import pytest
from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.errors.catalog import ProductNotFoundError
from memiro.application.manage_products import RemoveProduct
from memiro.entities.common.identifiers import ProductId
from tests.common.factory.catalog import PRODUCT
from tests.integration.manage_products.arrange import load_product
from tests.integration.prime import (
    StoredProductChildren,
    count_product_children_directly,
    prime_inquiry_for_the_product,
    prime_product_images,
    read_inquiry_item_directly,
)

pytestmark = pytest.mark.usefixtures("catalog")


async def _remove(container: AsyncContainer, product_id: ProductId = PRODUCT) -> None:
    """Execute one removal in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(RemoveProduct)
        await interactor.execute(product_id)


async def test_the_owner_removes_a_product_from_the_catalogue(container: AsyncContainer) -> None:
    """A removed product is gone from the catalogue the storefront reads."""
    await _remove(container)

    assert await load_product(container, PRODUCT) is None


async def test_a_removed_product_takes_its_photos_and_declarations_with_it(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """The children of a product are its own: none of them outlives it."""
    await prime_product_images(engine)

    await _remove(container)

    assert await count_product_children_directly(engine) == StoredProductChildren(declarations=0, images=0)


async def test_an_inquiry_keeps_its_names_when_the_product_it_named_is_gone(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """The position of a surviving inquiry loses the reference and keeps the snapshot."""
    await prime_inquiry_for_the_product(engine)

    await _remove(container)

    assert await read_inquiry_item_directly(engine) == (None, "Зеркало в раме")


async def test_removing_a_product_fails_if_it_does_not_exist(container: AsyncContainer) -> None:
    """PRODUCT_NOT_FOUND: a removal names a product that exists."""
    with pytest.raises(ProductNotFoundError):
        await _remove(container, product_id=uuid4())
