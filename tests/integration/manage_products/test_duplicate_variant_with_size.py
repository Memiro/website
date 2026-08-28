import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from dishka import AsyncContainer
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.common.gateway.catalog import ProductGateway
from memiro.application.common.input_limits import MAX_SIDE_MM
from memiro.application.errors.catalog import ProductNotFoundError, VariantNotFoundError
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.application.manage_products import (
    AddVariant,
    AddVariantForm,
    CreatedVariant,
    DuplicateVariantWithSize,
    DuplicateVariantWithSizeForm,
)
from memiro.entities.catalog.product.entity import Variant
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.errors.product import DuplicateVariantError, InvalidVariantConfigurationError
from tests.common.factory.catalog import PRODUCT
from tests.integration.prime import prime_incomplete_declaration, prime_no_pricing_settings, prime_size_surcharge

pytestmark = pytest.mark.usefixtures("catalog")
TWO_VARIANTS = 2


async def _add_source(container: AsyncContainer) -> CreatedVariant:
    """Arrange the source through the production add interactor."""
    async with container() as request:
        interactor = await request.get(AddVariant)
        return await interactor.execute(
            PRODUCT,
            AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=7),
        )


async def _duplicate(
    container: AsyncContainer,
    source: CreatedVariant,
    *,
    width_mm: int = 2200,
    height_mm: int = 600,
) -> CreatedVariant:
    """Duplicate one competitor in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(DuplicateVariantWithSize)
        return await interactor.execute(
            PRODUCT,
            source.id,
            DuplicateVariantWithSizeForm(width_mm=width_mm, height_mm=height_mm),
        )


async def test_the_owner_duplicates_a_variant_with_a_new_size_and_price(app: FastAPI) -> None:
    """A duplicate preserves configuration and order while receiving a new id and price."""
    container: AsyncContainer = app.state.dishka_container
    source = await _add_source(container)
    async with container() as request:
        duplicate = await request.get(DuplicateVariantWithSize)

        result = await duplicate.execute(
            PRODUCT,
            source.id,
            DuplicateVariantWithSizeForm(width_mm=2200, height_mm=600),
        )
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None
    duplicated = product.variant(result.id)
    assert duplicated is not None

    assert result.id != source.id
    assert duplicated == Variant(
        id=result.id,
        dimensions=Dimensions(
            width=Millimeters(value=2200),
            height=Millimeters(value=600),
        ),
        overrides=(),
        price=Money(amount=Decimal(18800)),
        sort_order=7,
    )
    assert product.price_from == Money(amount=Decimal(8900))
    assert len(product.variants) == TWO_VARIANTS


async def test_a_duplicated_variant_keeps_the_size_surcharge(
    app: FastAPI,
    engine: AsyncEngine,
) -> None:
    """The new child is recalculated with the size surcharge at its new dimensions."""
    container: AsyncContainer = app.state.dishka_container
    source = await _add_source(container)
    await prime_size_surcharge(engine)

    created = await _duplicate(container, source)
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None
    duplicate = product.variant(created.id)
    assert duplicate is not None

    assert duplicate.price == Money(amount=Decimal(20300))


async def test_concurrent_identical_duplications_preserve_variant_uniqueness(app: FastAPI) -> None:
    """Two competitors produce one copied child and one DUPLICATE_VARIANT refusal."""
    container: AsyncContainer = app.state.dishka_container
    source = await _add_source(container)

    results = await asyncio.gather(
        _duplicate(container, source),
        _duplicate(container, source),
        return_exceptions=True,
    )
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None

    assert sorted(type(result).__name__ for result in results) == [
        "CreatedVariant",
        "DuplicateVariantError",
    ]
    assert len(product.variants) == TWO_VARIANTS


def test_duplication_rejects_a_side_above_the_input_limit() -> None:
    """A side at MAX_SIDE_MM + 1 is rejected with VALIDATION_ERROR."""
    with pytest.raises(ValidationError):
        DuplicateVariantWithSizeForm(width_mm=MAX_SIDE_MM + 1, height_mm=600)


async def test_duplication_fails_if_pricing_settings_are_not_found(
    app: FastAPI,
    engine: AsyncEngine,
) -> None:
    """Missing pricing settings are rejected with PRICING_SETTINGS_NOT_FOUND."""
    container: AsyncContainer = app.state.dishka_container
    source = await _add_source(container)
    await prime_no_pricing_settings(engine)

    with pytest.raises(PricingSettingsNotFoundError):
        await _duplicate(container, source)


async def test_duplication_fails_if_the_product_became_incomplete(
    app: FastAPI,
    engine: AsyncEngine,
) -> None:
    """A no-longer-priceable source is rejected with INVALID_VARIANT_CONFIGURATION."""
    container: AsyncContainer = app.state.dishka_container
    source = await _add_source(container)
    await prime_incomplete_declaration(engine)

    with pytest.raises(InvalidVariantConfigurationError):
        await _duplicate(container, source)


async def test_duplication_fails_if_the_new_size_is_a_rotated_duplicate(app: FastAPI) -> None:
    """A rotated copy of the source is rejected with DUPLICATE_VARIANT."""
    container: AsyncContainer = app.state.dishka_container
    source = await _add_source(container)

    with pytest.raises(DuplicateVariantError):
        await _duplicate(container, source, width_mm=600, height_mm=800)


async def test_duplication_fails_if_the_product_is_not_found(
    request_container: AsyncContainer,
) -> None:
    """An unknown product is rejected with PRODUCT_NOT_FOUND."""
    interactor = await request_container.get(DuplicateVariantWithSize)

    with pytest.raises(ProductNotFoundError):
        await interactor.execute(
            uuid4(),
            uuid4(),
            DuplicateVariantWithSizeForm(width_mm=800, height_mm=600),
        )


async def test_duplication_fails_if_the_variant_is_not_found(app: FastAPI) -> None:
    """An unknown child is rejected with VARIANT_NOT_FOUND."""
    container: AsyncContainer = app.state.dishka_container
    await _add_source(container)
    async with container() as request:
        interactor = await request.get(DuplicateVariantWithSize)

        with pytest.raises(VariantNotFoundError):
            await interactor.execute(
                PRODUCT,
                uuid4(),
                DuplicateVariantWithSizeForm(width_mm=2200, height_mm=600),
            )
