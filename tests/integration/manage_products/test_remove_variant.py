import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from dishka import AsyncContainer
from fastapi import FastAPI

from memiro.application.common.gateway.catalog import ProductGateway
from memiro.application.errors.catalog import ProductNotFoundError, VariantNotFoundError
from memiro.application.manage_products import AddVariant, AddVariantForm, CreatedVariant, RemoveVariant
from memiro.entities.catalog.product.entity import Variant
from memiro.entities.common.identifiers import VariantId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from tests.common.factory.catalog import PRODUCT

pytestmark = pytest.mark.usefixtures("catalog")


async def _add(container: AsyncContainer, *, width_mm: int, height_mm: int) -> CreatedVariant:
    """Arrange one variant through the production add interactor."""
    async with container() as request:
        interactor = await request.get(AddVariant)
        return await interactor.execute(
            PRODUCT,
            AddVariantForm(
                width_mm=width_mm,
                height_mm=height_mm,
                overrides=[],
                sort_order=0,
            ),
        )


async def _remove(container: AsyncContainer, variant_id: VariantId) -> None:
    """Remove one competitor in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(RemoveVariant)
        await interactor.execute(PRODUCT, variant_id)


async def test_removing_the_cheapest_variant_raises_the_product_price(app: FastAPI) -> None:
    """Removing the cheapest variant derives the price from the remaining child."""
    container: AsyncContainer = app.state.dishka_container
    cheapest = await _add(container, width_mm=800, height_mm=600)
    remaining = await _add(container, width_mm=1200, height_mm=800)
    async with container() as request:
        interactor = await request.get(RemoveVariant)

        await interactor.execute(PRODUCT, cheapest.id)
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None

    assert product.price_from == Money(amount=Decimal(13700))
    assert product.variants == (
        Variant(
            remaining.id,
            dimensions=Dimensions(
                width=Millimeters(value=1200),
                height=Millimeters(value=800),
            ),
            overrides=(),
            price=Money(amount=Decimal(13700)),
            sort_order=0,
        ),
    )


async def test_removing_the_last_variant_leaves_the_product_without_a_price(app: FastAPI) -> None:
    """Removing the last child stores NULL rather than a placeholder price."""
    container: AsyncContainer = app.state.dishka_container
    only = await _add(container, width_mm=800, height_mm=600)

    await _remove(container, only.id)
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None

    assert product.price_from is None
    assert product.variants == ()


async def test_concurrent_removals_preserve_one_atomic_result(app: FastAPI) -> None:
    """Two competitors removing one child produce one success and one VARIANT_NOT_FOUND."""
    container: AsyncContainer = app.state.dishka_container
    only = await _add(container, width_mm=800, height_mm=600)

    results = await asyncio.gather(
        _remove(container, only.id),
        _remove(container, only.id),
        return_exceptions=True,
    )
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None

    assert sorted(type(result).__name__ for result in results) == [
        "NoneType",
        "VariantNotFoundError",
    ]
    assert product.variants == ()
    assert product.price_from is None


async def test_removing_fails_if_the_product_is_not_found(
    request_container: AsyncContainer,
) -> None:
    """An unknown product is rejected with PRODUCT_NOT_FOUND."""
    interactor = await request_container.get(RemoveVariant)

    with pytest.raises(ProductNotFoundError):
        await interactor.execute(uuid4(), uuid4())


async def test_removing_fails_if_the_variant_is_not_found(app: FastAPI) -> None:
    """An unknown child is rejected with VARIANT_NOT_FOUND."""
    container: AsyncContainer = app.state.dishka_container
    await _add(container, width_mm=800, height_mm=600)
    async with container() as request:
        interactor = await request.get(RemoveVariant)

        with pytest.raises(VariantNotFoundError):
            await interactor.execute(PRODUCT, uuid4())
