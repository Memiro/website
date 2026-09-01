import asyncio
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from dishka import AsyncContainer
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.input_limits import MAX_SIDE_MM, MIN_SIDE_MM
from memiro.application.errors.catalog import ProductNotFoundError, VariantNotFoundError
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.application.manage_products import (
    AddVariant,
    AddVariantForm,
    CreatedVariant,
    DuplicateVariantWithSize,
    DuplicateVariantWithSizeForm,
)
from memiro.application.manage_products.shared import VariantOverrideForm
from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.catalog.product.entity import DeclaredValue, Variant
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.errors.product import DuplicateVariantError, InvalidVariantConfigurationError
from tests.common.factory.catalog import BLADE, GRAPHITE, PRODUCT
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


def _expected_variant(
    variant_id: UUID,
    *,
    width_mm: int,
    height_mm: int,
    price: str,
    overrides: tuple[DeclaredValue, ...] = (),
) -> Variant:
    """Build the complete child state expected from duplication."""
    return Variant(
        variant_id,
        dimensions=Dimensions(
            width=Millimeters(value=width_mm),
            height=Millimeters(value=height_mm),
        ),
        overrides=overrides,
        price=Money(amount=Decimal(price)),
        sort_order=7,
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
    assert product.variant(source.id) == _expected_variant(
        source.id,
        width_mm=800,
        height_mm=600,
        price="8900",
    )
    assert duplicated == _expected_variant(result.id, width_mm=2200, height_mm=600, price="18800")
    assert product.price_from == Money(amount=Decimal(8900))
    assert len(product.variants) == TWO_VARIANTS


async def test_a_duplicated_variant_keeps_the_overrides_of_its_source(app: FastAPI) -> None:
    """A copy of an overridden child keeps the override and is priced by it."""
    container: AsyncContainer = app.state.dishka_container
    async with container() as request:
        add = await request.get(AddVariant)
        source = await add.execute(
            PRODUCT,
            AddVariantForm(
                width_mm=800,
                height_mm=600,
                overrides=[VariantOverrideForm(attribute_id=BLADE, value_id=GRAPHITE)],
                sort_order=7,
            ),
        )

    created = await _duplicate(container, source)
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None
    duplicate = product.variant(created.id)
    assert duplicate is not None

    darker_blade = (DeclaredValue(attribute_id=BLADE, chosen=ChosenValue(value_id=GRAPHITE, quantity=None)),)
    assert product.variant(source.id) == _expected_variant(
        source.id,
        width_mm=800,
        height_mm=600,
        price="10100",
        overrides=darker_blade,
    )
    assert duplicate == _expected_variant(
        created.id,
        width_mm=2200,
        height_mm=600,
        price="22100",
        overrides=darker_blade,
    )


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

    assert product.variant(source.id) == _expected_variant(
        source.id,
        width_mm=800,
        height_mm=600,
        price="8900",
    )
    assert duplicate == _expected_variant(created.id, width_mm=2200, height_mm=600, price="20300")
    assert product.price_from == Money(amount=Decimal(8900))
    assert len(product.variants) == TWO_VARIANTS


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

    created, duplicate_error = sorted(results, key=lambda result: type(result).__name__)
    assert isinstance(created, CreatedVariant)
    assert isinstance(duplicate_error, DuplicateVariantError)
    assert product.variant(source.id) == _expected_variant(
        source.id,
        width_mm=800,
        height_mm=600,
        price="8900",
    )
    assert product.variant(created.id) == _expected_variant(
        created.id,
        width_mm=2200,
        height_mm=600,
        price="18800",
    )
    assert product.price_from == Money(amount=Decimal(8900))
    assert len(product.variants) == TWO_VARIANTS


def test_duplication_rejects_a_side_above_the_input_limit() -> None:
    """A side at MAX_SIDE_MM + 1 is rejected with VALIDATION_ERROR."""
    with pytest.raises(ValidationError):
        DuplicateVariantWithSizeForm(width_mm=MAX_SIDE_MM + 1, height_mm=600)


def test_duplication_rejects_a_side_below_the_input_limit() -> None:
    """A side at MIN_SIDE_MM - 1 is rejected with VALIDATION_ERROR."""
    with pytest.raises(ValidationError):
        DuplicateVariantWithSizeForm(width_mm=MIN_SIDE_MM - 1, height_mm=600)


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
