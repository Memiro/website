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
from memiro.application.errors.catalog import (
    AttributeValueNotFoundError,
    ProductNotFoundError,
    VariantNotFoundError,
)
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.application.manage_products import (
    AddVariant,
    AddVariantForm,
    ChangeVariant,
    ChangeVariantForm,
)
from memiro.application.manage_products.shared import VariantOverrideForm
from memiro.entities.catalog.product.entity import Variant
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.errors.product import (
    DuplicateVariantError,
    InvalidVariantConfigurationError,
    InvalidVariantSortOrderError,
)
from tests.common.factory.catalog import PRODUCT
from tests.integration.prime import prime_incomplete_declaration, prime_no_pricing_settings

pytestmark = pytest.mark.usefixtures("catalog")
TWO_VARIANTS = 2


async def _add_variant(container: AsyncContainer) -> Variant:
    """Arrange one canonical variant through its production interactor."""
    async with container() as request:
        add = await request.get(AddVariant)
        created = await add.execute(
            PRODUCT,
            AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=2),
        )
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None
    assert product.variants[0].id == created.id
    return product.variants[0]


async def _add_at(
    container: AsyncContainer,
    *,
    width_mm: int,
    height_mm: int,
) -> Variant:
    """Arrange a variant of a named size through AddVariant."""
    async with container() as request:
        add = await request.get(AddVariant)
        created = await add.execute(
            PRODUCT,
            AddVariantForm(width_mm=width_mm, height_mm=height_mm, overrides=[], sort_order=0),
        )
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None
    variant = product.variant(created.id)
    assert variant is not None
    return variant


async def _change_to(container: AsyncContainer, variant: Variant) -> None:
    """Change one competitor to the shared target configuration."""
    async with container() as request:
        change = await request.get(ChangeVariant)
        await change.execute(
            PRODUCT,
            variant.id,
            ChangeVariantForm(width_mm=1600, height_mm=900, overrides=[], sort_order=0),
        )


async def test_the_owner_changes_a_variant_and_its_derived_product_price(app: FastAPI) -> None:
    """Changing a variant preserves its id and stores the newly calculated price."""
    container: AsyncContainer = app.state.dishka_container
    original = await _add_variant(container)
    async with container() as request:
        change = await request.get(ChangeVariant)

        await change.execute(
            PRODUCT,
            original.id,
            ChangeVariantForm(width_mm=1200, height_mm=800, overrides=[], sort_order=5),
        )
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None

    assert product.price_from == Money(amount=Decimal(13700))
    assert product.variants == (
        Variant(
            id=original.id,
            dimensions=Dimensions(
                width=Millimeters(value=1200),
                height=Millimeters(value=800),
            ),
            overrides=(),
            price=Money(amount=Decimal(13700)),
            sort_order=5,
        ),
    )


async def test_concurrent_changes_preserve_variant_uniqueness(app: FastAPI) -> None:
    """Two competitors converging on one configuration produce one DUPLICATE_VARIANT."""
    container: AsyncContainer = app.state.dishka_container
    first = await _add_at(container, width_mm=800, height_mm=600)
    second = await _add_at(container, width_mm=1200, height_mm=800)

    results = await asyncio.gather(
        _change_to(container, first),
        _change_to(container, second),
        return_exceptions=True,
    )
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None

    assert sorted(type(result).__name__ for result in results) == [
        "DuplicateVariantError",
        "NoneType",
    ]
    assert len(product.variants) == TWO_VARIANTS


def test_changing_rejects_a_side_above_the_input_limit() -> None:
    """A side at MAX_SIDE_MM + 1 is rejected with VALIDATION_ERROR."""
    with pytest.raises(ValidationError):
        ChangeVariantForm(
            width_mm=MAX_SIDE_MM + 1,
            height_mm=600,
            overrides=[],
            sort_order=0,
        )


async def test_changing_fails_if_pricing_settings_are_not_found(
    app: FastAPI,
    engine: AsyncEngine,
) -> None:
    """Missing pricing settings are rejected with PRICING_SETTINGS_NOT_FOUND."""
    container: AsyncContainer = app.state.dishka_container
    variant = await _add_variant(container)
    await prime_no_pricing_settings(engine)
    async with container() as request:
        interactor = await request.get(ChangeVariant)

        with pytest.raises(PricingSettingsNotFoundError):
            await interactor.execute(
                PRODUCT,
                variant.id,
                ChangeVariantForm(width_mm=1200, height_mm=800, overrides=[], sort_order=0),
            )


async def test_changing_fails_if_an_override_is_outside_the_product_dictionary(
    app: FastAPI,
) -> None:
    """An unknown override is rejected with ATTRIBUTE_VALUE_NOT_FOUND."""
    container: AsyncContainer = app.state.dishka_container
    variant = await _add_variant(container)
    async with container() as request:
        change = await request.get(ChangeVariant)

        with pytest.raises(AttributeValueNotFoundError):
            await change.execute(
                PRODUCT,
                variant.id,
                ChangeVariantForm(
                    width_mm=800,
                    height_mm=600,
                    overrides=[VariantOverrideForm(attribute_id=uuid4(), value_id=uuid4())],
                    sort_order=0,
                ),
            )


async def test_changing_fails_if_the_resulting_configuration_is_incomplete(
    app: FastAPI,
    engine: AsyncEngine,
) -> None:
    """An incomplete result is rejected with INVALID_VARIANT_CONFIGURATION."""
    container: AsyncContainer = app.state.dishka_container
    variant = await _add_variant(container)
    await prime_incomplete_declaration(engine)
    async with container() as request:
        change = await request.get(ChangeVariant)

        with pytest.raises(InvalidVariantConfigurationError):
            await change.execute(
                PRODUCT,
                variant.id,
                ChangeVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0),
            )


async def test_changing_fails_if_the_owner_order_is_negative(app: FastAPI) -> None:
    """A negative order is rejected with INVALID_VARIANT_SORT_ORDER."""
    container: AsyncContainer = app.state.dishka_container
    variant = await _add_variant(container)
    async with container() as request:
        change = await request.get(ChangeVariant)

        with pytest.raises(InvalidVariantSortOrderError):
            await change.execute(
                PRODUCT,
                variant.id,
                ChangeVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=-1),
            )


async def test_changing_fails_if_it_duplicates_a_neighbour(app: FastAPI) -> None:
    """A conflicting replacement is rejected with DUPLICATE_VARIANT without mutation."""
    container: AsyncContainer = app.state.dishka_container
    existing = await _add_at(container, width_mm=800, height_mm=600)
    changed = await _add_at(container, width_mm=1200, height_mm=800)
    async with container() as request:
        change = await request.get(ChangeVariant)

        with pytest.raises(DuplicateVariantError):
            await change.execute(
                PRODUCT,
                changed.id,
                ChangeVariantForm(
                    width_mm=existing.dimensions.height.value,
                    height_mm=existing.dimensions.width.value,
                    overrides=[],
                    sort_order=0,
                ),
            )
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None

    assert product.variant(changed.id) == changed


async def test_changing_fails_if_the_product_is_not_found(
    request_container: AsyncContainer,
) -> None:
    """An unknown product is rejected with PRODUCT_NOT_FOUND."""
    change = await request_container.get(ChangeVariant)

    with pytest.raises(ProductNotFoundError):
        await change.execute(
            uuid4(),
            uuid4(),
            ChangeVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0),
        )


async def test_changing_fails_if_the_variant_is_not_found(app: FastAPI) -> None:
    """An unknown child is rejected with VARIANT_NOT_FOUND."""
    container: AsyncContainer = app.state.dishka_container
    await _add_variant(container)
    async with container() as request:
        change = await request.get(ChangeVariant)

        with pytest.raises(VariantNotFoundError):
            await change.execute(
                PRODUCT,
                uuid4(),
                ChangeVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0),
            )
