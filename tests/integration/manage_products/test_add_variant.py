import asyncio
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from dishka import AsyncContainer
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.adapters.db.tables import product_variants_table
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.input_limits import MAX_SELECTIONS, MAX_SIDE_MM, MIN_SIDE_MM
from memiro.application.errors.catalog import AttributeValueNotFoundError, ProductNotFoundError
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.application.manage_products import AddVariant, AddVariantForm, CreatedVariant
from memiro.application.manage_products.shared import VariantOverrideForm
from memiro.entities.catalog.product.entity import Product, Variant
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.errors.product import (
    DuplicateVariantError,
    InvalidVariantConfigurationError,
    InvalidVariantSortOrderError,
)
from tests.common.factory.catalog import BLADE, GRAPHITE, HEATING, PRODUCT, WITH_HEATING
from tests.integration.prime import (
    prime_hidden_calculated_price,
    prime_incomplete_declaration,
    prime_no_pricing_settings,
    prime_product_publication,
    prime_production_limits,
    prime_size_surcharge,
)

pytestmark = pytest.mark.usefixtures("catalog")


async def _add(container: AsyncContainer, form: AddVariantForm) -> CreatedVariant:
    """Execute one add in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(AddVariant)
        return await interactor.execute(PRODUCT, form)


async def _copy_variant_row_directly(engine: AsyncEngine, variant_id: UUID) -> None:
    """Insert a row-for-row copy of one variant under a fresh identifier."""
    async with engine.begin() as connection:
        result = await connection.execute(
            select(product_variants_table).where(product_variants_table.c.id == variant_id),
        )
        row = dict(result.mappings().one())
        await connection.execute(insert(product_variants_table), [{**row, "id": uuid4()}])


async def _load_product(container: AsyncContainer) -> Product | None:
    """Read the aggregate in a fresh transaction after a command."""
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        return await gateway.get(PRODUCT, eager_variants=True)


def _expected_variant(
    variant_id: UUID,
    *,
    width_mm: int,
    height_mm: int,
    price: str,
    sort_order: int = 0,
) -> Variant:
    """Build the complete child state expected from a command."""
    return Variant(
        variant_id,
        dimensions=Dimensions(
            width=Millimeters(value=width_mm),
            height=Millimeters(value=height_mm),
        ),
        overrides=(),
        price=Money(amount=Decimal(price)),
        sort_order=sort_order,
    )


async def test_the_owner_adds_a_variant_priced_by_the_workbook(
    app: FastAPI,
) -> None:
    """The owner saves the 8,900 rouble workbook variant and its derived product price."""
    container: AsyncContainer = app.state.dishka_container
    async with container() as request:
        interactor = await request.get(AddVariant)
        result = await interactor.execute(
            PRODUCT,
            AddVariantForm(
                width_mm=800,
                height_mm=600,
                overrides=[],
                sort_order=2,
            ),
        )
    async with container() as request:
        gateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None
    variant = product.variants[0]

    assert result == CreatedVariant(id=variant.id)
    assert product.price_from == Money(amount=Decimal(8900))
    assert product.variants == (_expected_variant(variant.id, width_mm=800, height_mm=600, price="8900", sort_order=2),)


async def test_adding_a_variant_marks_the_stored_product_as_changed(
    app: FastAPI,
) -> None:
    """The audit date a variant command moves travels to the database."""
    container: AsyncContainer = app.state.dishka_container

    await _add(container, AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0))

    product = await _load_product(container)
    assert product is not None
    assert product.updated_at > product.created_at


async def test_the_owner_prices_an_unpublished_hidden_variant_beyond_customer_limits(
    engine: AsyncEngine,
    app: FastAPI,
) -> None:
    """Owner pricing bypasses publication, hiding and production-limit gates."""
    await prime_product_publication(engine, is_published=False)
    await prime_hidden_calculated_price(engine)
    await prime_production_limits(
        engine,
        max_long_side_mm=Millimeters(value=500),
        max_short_side_mm=Millimeters(value=500),
    )
    container: AsyncContainer = app.state.dishka_container

    result = await _add(
        container,
        AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0),
    )
    product = await _load_product(container)

    assert product is not None
    assert result == CreatedVariant(id=product.variants[0].id)
    assert product.price_from == Money(amount=Decimal(8900))
    assert product.variants == (_expected_variant(result.id, width_mm=800, height_mm=600, price="8900"),)


async def test_the_owner_variant_keeps_the_size_surcharge(
    engine: AsyncEngine,
    app: FastAPI,
) -> None:
    """Owner pricing applies the same size surcharge as every other pricing caller."""
    await prime_size_surcharge(engine)
    container: AsyncContainer = app.state.dishka_container

    result = await _add(
        container,
        AddVariantForm(width_mm=2200, height_mm=600, overrides=[], sort_order=0),
    )
    product = await _load_product(container)

    assert product is not None
    assert product.price_from == Money(amount=Decimal(20300))
    assert product.variants == (_expected_variant(result.id, width_mm=2200, height_mm=600, price="20300"),)


async def test_concurrent_identical_additions_preserve_variant_uniqueness(
    app: FastAPI,
) -> None:
    """Two competitors produce one variant and one DUPLICATE_VARIANT refusal."""
    container: AsyncContainer = app.state.dishka_container
    form = AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0)

    results = await asyncio.gather(
        _add(container, form),
        _add(container, form),
        return_exceptions=True,
    )
    product = await _load_product(container)

    assert sorted(type(result).__name__ for result in results) == [
        "CreatedVariant",
        "DuplicateVariantError",
    ]
    assert product is not None
    assert product.price_from == Money(amount=Decimal(8900))
    assert product.variants == (_expected_variant(product.variants[0].id, width_mm=800, height_mm=600, price="8900"),)


async def test_the_database_refuses_a_second_variant_with_the_same_fingerprint(
    app: FastAPI,
    engine: AsyncEngine,
) -> None:
    """The unique fingerprint constraint stands even when no aggregate lock serialized the writers."""
    container: AsyncContainer = app.state.dishka_container
    created = await _add(container, AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0))

    with pytest.raises(IntegrityError):
        await _copy_variant_row_directly(engine, created.id)


def test_adding_rejects_a_side_above_the_input_limit() -> None:
    """A side at MAX_SIDE_MM + 1 is rejected with VALIDATION_ERROR."""
    with pytest.raises(ValidationError):
        AddVariantForm(
            width_mm=MAX_SIDE_MM + 1,
            height_mm=600,
            overrides=[],
            sort_order=0,
        )


def test_adding_rejects_a_side_below_the_input_limit() -> None:
    """A side at MIN_SIDE_MM - 1 is rejected with VALIDATION_ERROR."""
    with pytest.raises(ValidationError):
        AddVariantForm(
            width_mm=MIN_SIDE_MM - 1,
            height_mm=600,
            overrides=[],
            sort_order=0,
        )


def test_adding_rejects_more_than_the_selection_limit() -> None:
    """Overrides at MAX_SELECTIONS + 1 are rejected with VALIDATION_ERROR."""
    with pytest.raises(ValidationError):
        AddVariantForm(
            width_mm=800,
            height_mm=600,
            overrides=[VariantOverrideForm(attribute_id=uuid4(), value_id=uuid4()) for _ in range(MAX_SELECTIONS + 1)],
            sort_order=0,
        )


def test_adding_rejects_two_overrides_of_one_attribute() -> None:
    """Two overrides of one attribute are rejected with VALIDATION_ERROR."""
    with pytest.raises(ValidationError):
        AddVariantForm(
            width_mm=800,
            height_mm=600,
            overrides=[
                VariantOverrideForm(attribute_id=BLADE, value_id=GRAPHITE),
                VariantOverrideForm(attribute_id=BLADE, value_id=GRAPHITE),
            ],
            sort_order=0,
        )


def test_adding_rejects_an_override_with_two_representations() -> None:
    """An override with a value and quantity is rejected with VALIDATION_ERROR."""
    with pytest.raises(ValidationError):
        VariantOverrideForm(
            attribute_id=BLADE,
            value_id=GRAPHITE,
            quantity=Decimal(1),
        )


def test_adding_rejects_an_override_without_a_representation() -> None:
    """An override without a value or quantity is rejected with VALIDATION_ERROR."""
    with pytest.raises(ValidationError):
        VariantOverrideForm(attribute_id=BLADE)


async def test_adding_fails_if_pricing_settings_are_not_found(
    engine: AsyncEngine,
    request_container: AsyncContainer,
) -> None:
    """Missing pricing settings are rejected with PRICING_SETTINGS_NOT_FOUND."""
    await prime_no_pricing_settings(engine)
    interactor = await request_container.get(AddVariant)

    with pytest.raises(PricingSettingsNotFoundError):
        await interactor.execute(
            PRODUCT,
            AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0),
        )


async def test_adding_fails_if_an_override_is_outside_the_product_dictionary(
    request_container: AsyncContainer,
) -> None:
    """An unknown override is rejected with ATTRIBUTE_VALUE_NOT_FOUND."""
    interactor = await request_container.get(AddVariant)

    with pytest.raises(AttributeValueNotFoundError):
        await interactor.execute(
            PRODUCT,
            AddVariantForm(
                width_mm=800,
                height_mm=600,
                overrides=[VariantOverrideForm(attribute_id=uuid4(), value_id=uuid4())],
                sort_order=0,
            ),
        )


async def test_adding_fails_if_an_override_replaces_nothing_the_product_declared(
    request_container: AsyncContainer,
) -> None:
    """An override of an attribute the product never declared is rejected with ATTRIBUTE_VALUE_NOT_FOUND."""
    interactor = await request_container.get(AddVariant)

    with pytest.raises(AttributeValueNotFoundError):
        await interactor.execute(
            PRODUCT,
            AddVariantForm(
                width_mm=800,
                height_mm=600,
                overrides=[VariantOverrideForm(attribute_id=HEATING, value_id=WITH_HEATING)],
                sort_order=0,
            ),
        )


async def test_adding_fails_if_the_resulting_configuration_is_incomplete(
    engine: AsyncEngine,
    request_container: AsyncContainer,
) -> None:
    """An incomplete result is rejected with INVALID_VARIANT_CONFIGURATION."""
    await prime_incomplete_declaration(engine)
    interactor = await request_container.get(AddVariant)

    with pytest.raises(InvalidVariantConfigurationError):
        await interactor.execute(
            PRODUCT,
            AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0),
        )


async def test_adding_fails_if_the_owner_order_is_negative(
    request_container: AsyncContainer,
) -> None:
    """A negative order is rejected with INVALID_VARIANT_SORT_ORDER."""
    interactor = await request_container.get(AddVariant)

    with pytest.raises(InvalidVariantSortOrderError):
        await interactor.execute(
            PRODUCT,
            AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=-1),
        )


async def test_adding_fails_if_the_variant_already_exists(
    app: FastAPI,
) -> None:
    """A sequential duplicate is rejected with DUPLICATE_VARIANT."""
    container: AsyncContainer = app.state.dishka_container
    form = AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0)
    await _add(container, form)

    with pytest.raises(DuplicateVariantError):
        await _add(container, form)


async def test_adding_fails_if_the_product_is_not_found(
    request_container: AsyncContainer,
) -> None:
    """An unknown product is rejected with PRODUCT_NOT_FOUND."""
    interactor = await request_container.get(AddVariant)

    with pytest.raises(ProductNotFoundError):
        await interactor.execute(
            uuid4(),
            AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0),
        )
