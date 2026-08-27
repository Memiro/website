from decimal import Decimal
from uuid import uuid4

import pytest

from memiro.application.calculate_price import (
    CalculatedPrice,
    CalculatePriceForm,
    Selection,
    SelectionDelta,
)
from memiro.application.common.input_limits import MAX_SIDE_MM
from memiro.entities.pricing.quotation import PricingVerdict
from tests.common.factory.catalog import ALUMINIUM, BLADE, GRAPHITE, PRODUCT
from tests.integration.api_client import ApiClient

pytestmark = pytest.mark.usefixtures("catalog")


def _form(**overrides: object) -> CalculatePriceForm:
    """Build the canonical request — 800 x 600 of the demo mirror — with the test's own changes."""
    return CalculatePriceForm(
        product_id=PRODUCT,
        width_mm=800,
        height_mm=600,
        selections=[],
    ).model_copy(update=overrides)


async def test_a_customer_sees_the_price_the_workbook_shows(api_client: ApiClient) -> None:
    """The canonical case of the xlsx workbook answers 8 900 RUB with the verdict PRICED."""
    response = await api_client.calculate(_form())

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.PRICED,
        total=Decimal(8900),
        selection_deltas=[],
    )


async def test_a_customer_sees_what_a_darker_blade_adds(api_client: ApiClient) -> None:
    """Graphite instead of the product's silver is answered with its own signed delta."""
    selection = Selection(attribute_id=BLADE, value_id=GRAPHITE)

    response = await api_client.calculate(_form(selections=[selection]))

    # 0.48 m2 x 7000 + 2.8 lm x 2200 + 500 = 10 020 -> 10 100; the blade
    # itself costs (7000 - 4500) x 0.48 m2 = 1 200 more than the default.
    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.PRICED,
        total=Decimal(10100),
        selection_deltas=[SelectionDelta(attribute_id=BLADE, value_id=GRAPHITE, delta=Decimal(1200))],
    )


async def test_the_answer_says_nothing_about_how_the_price_is_made(api_client: ApiClient) -> None:
    """The public projection carries no tariffs, no factors and no lines of blade and edge."""
    response = await api_client.calculate(_form())

    body = response.text
    assert "4500" not in body
    assert "2200" not in body
    assert "breakdown" not in body
    assert "rate" not in body


async def test_pricing_fails_if_the_product_is_unknown(api_client: ApiClient) -> None:
    """An identifier nobody issued is refused with PRODUCT_NOT_FOUND."""
    response = await api_client.calculate(_form(product_id=uuid4()))

    response.assert_error(404, "PRODUCT_NOT_FOUND")


async def test_pricing_fails_if_the_chosen_value_belongs_to_another_attribute(api_client: ApiClient) -> None:
    """An aluminium frame chosen as a blade is refused with ATTRIBUTE_VALUE_NOT_FOUND."""
    selection = Selection(attribute_id=BLADE, value_id=ALUMINIUM)

    response = await api_client.calculate(_form(selections=[selection]))

    response.assert_error(404, "ATTRIBUTE_VALUE_NOT_FOUND")


async def test_pricing_fails_if_the_chosen_value_does_not_exist(api_client: ApiClient) -> None:
    """A value nobody issued is refused with ATTRIBUTE_VALUE_NOT_FOUND."""
    selection = Selection(attribute_id=BLADE, value_id=uuid4())

    response = await api_client.calculate(_form(selections=[selection]))

    response.assert_error(404, "ATTRIBUTE_VALUE_NOT_FOUND")


async def test_pricing_fails_if_a_side_is_beyond_the_input_bound(api_client: ApiClient) -> None:
    """A side one millimetre over the form's bound is refused with VALIDATION_ERROR."""
    dishonest = CalculatePriceForm.model_construct(
        product_id=PRODUCT,
        width_mm=MAX_SIDE_MM + 1,
        height_mm=600,
        selections=[],
    )

    response = await api_client.calculate(dishonest)

    response.assert_error(422, "VALIDATION_ERROR")


async def test_pricing_fails_if_a_side_is_zero(api_client: ApiClient) -> None:
    """A product with no side does not exist, and the form refuses it with VALIDATION_ERROR."""
    dishonest = CalculatePriceForm.model_construct(
        product_id=PRODUCT,
        width_mm=0,
        height_mm=600,
        selections=[],
    )

    response = await api_client.calculate(dishonest)

    response.assert_error(422, "VALIDATION_ERROR")
