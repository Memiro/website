from decimal import Decimal
from uuid import uuid4

import pytest
from dishka import AsyncContainer
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.input_limits import MAX_SIDE_MM
from memiro.application.errors.catalog import AttributeValueNotFoundError, ProductNotFoundError
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.application.manage_products import (
    AddVariant,
    AddVariantForm,
    QuotedVariant,
    QuoteVariant,
    QuoteVariantForm,
)
from memiro.application.manage_products.shared import VariantOverrideForm
from memiro.entities.errors.product import InvalidVariantConfigurationError
from tests.common.factory.catalog import BLADE, GRAPHITE, PRODUCT
from tests.integration.prime import prime_incomplete_declaration, prime_no_pricing_settings

pytestmark = pytest.mark.usefixtures("catalog")


async def test_the_owner_sees_the_price_of_a_variant_he_has_not_saved_yet(
    request_container: AsyncContainer,
) -> None:
    """The workbook variant is quoted at its 8,900 roubles before anybody saves it."""
    interactor = await request_container.get(QuoteVariant)

    quoted = await interactor.execute(
        PRODUCT,
        QuoteVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0),
    )

    assert quoted == QuotedVariant(price=Decimal(8900))


async def test_the_quoted_price_is_the_price_the_variant_is_saved_with(
    container: AsyncContainer,
) -> None:
    """The panel and the command answer one question with one number (ADR-0011)."""
    overrides = [VariantOverrideForm(attribute_id=BLADE, value_id=GRAPHITE)]
    async with container() as request:
        quoting = await request.get(QuoteVariant)
        quoted = await quoting.execute(
            PRODUCT,
            QuoteVariantForm(width_mm=900, height_mm=700, overrides=overrides, sort_order=0),
        )

    async with container() as request:
        adding = await request.get(AddVariant)
        created = await adding.execute(
            PRODUCT,
            AddVariantForm(width_mm=900, height_mm=700, overrides=overrides, sort_order=0),
        )

    async with container() as request:
        gateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None
    saved = product.variant(created.id)
    assert saved is not None
    assert quoted.price == saved.price.amount


async def test_quoting_a_variant_writes_nothing(container: AsyncContainer) -> None:
    """A question is not a command: the product keeps the variants it had."""
    async with container() as request:
        interactor = await request.get(QuoteVariant)
        await interactor.execute(
            PRODUCT,
            QuoteVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0),
        )

    async with container() as request:
        gateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None
    assert product.variants == ()
    assert product.price_from is None


def test_quoting_rejects_a_side_above_the_input_limit() -> None:
    """The panel is refused the size the command would refuse: VALIDATION_ERROR."""
    with pytest.raises(ValidationError):
        QuoteVariantForm(width_mm=MAX_SIDE_MM + 1, height_mm=600, overrides=[], sort_order=0)


async def test_quoting_fails_if_the_product_is_unknown(request_container: AsyncContainer) -> None:
    """A quotation for an identifier nobody issued is rejected with PRODUCT_NOT_FOUND."""
    interactor = await request_container.get(QuoteVariant)

    with pytest.raises(ProductNotFoundError):
        await interactor.execute(
            uuid4(),
            QuoteVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0),
        )


async def test_quoting_fails_if_an_override_replaces_nothing_the_product_declared(
    request_container: AsyncContainer,
) -> None:
    """An override of an attribute the product never declared is rejected with ATTRIBUTE_VALUE_NOT_FOUND."""
    interactor = await request_container.get(QuoteVariant)

    with pytest.raises(AttributeValueNotFoundError):
        await interactor.execute(
            PRODUCT,
            QuoteVariantForm(
                width_mm=800,
                height_mm=600,
                overrides=[VariantOverrideForm(attribute_id=uuid4(), value_id=uuid4())],
                sort_order=0,
            ),
        )


async def test_quoting_fails_if_the_resulting_configuration_is_incomplete(
    engine: AsyncEngine,
    request_container: AsyncContainer,
) -> None:
    """A configuration the calculator cannot price is rejected with INVALID_VARIANT_CONFIGURATION."""
    await prime_incomplete_declaration(engine)
    interactor = await request_container.get(QuoteVariant)

    with pytest.raises(InvalidVariantConfigurationError):
        await interactor.execute(
            PRODUCT,
            QuoteVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0),
        )


async def test_quoting_fails_if_pricing_settings_are_not_found(
    engine: AsyncEngine,
    request_container: AsyncContainer,
) -> None:
    """A quotation before the pricing setup is rejected with PRICING_SETTINGS_NOT_FOUND."""
    await prime_no_pricing_settings(engine)
    interactor = await request_container.get(QuoteVariant)

    with pytest.raises(PricingSettingsNotFoundError):
        await interactor.execute(
            PRODUCT,
            QuoteVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0),
        )
