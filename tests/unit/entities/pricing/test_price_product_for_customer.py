from dataclasses import replace
from decimal import Decimal

import pytest
from hypothesis import given, settings

from memiro.entities.catalog.attribute.rate import Unit
from memiro.entities.catalog.product.entity import ConfiguredValue, DeclaredValue, Product
from memiro.entities.common.identifiers import AttributeValueId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.pricing.pricing_service import price_product_for_customer
from memiro.entities.pricing.pricing_settings import PricingSettings
from memiro.entities.pricing.quotation import PricingVerdict, Quotation
from tests.common.factory.catalog import (
    BACKLIGHT,
    BLADE,
    CONTOUR,
    CUTOUT,
    CUTOUTS,
    FRAME,
    HEATING,
    NO_BACKLIGHT,
    NO_FRAME,
    NO_HEATING,
    SILVER,
    WITH_HEATING,
    demo_attributes,
    demo_attributes_with_changeability,
    demo_cutouts,
    demo_numeric_product,
    demo_product,
    demo_product_with_value,
    demo_settings,
    product_with_added_declaration,
)
from tests.common.pricing_expected import canonical_quotation, quotation_line
from tests.unit.composite import customer_gate_cases, fractional_quantities, rotated_limit_cases


def _dimensions(width: int, height: int) -> Dimensions:
    return Dimensions(width=Millimeters(value=width), height=Millimeters(value=height))


def test_an_unpublished_product_is_not_priceable_for_a_customer() -> None:
    """A customer receives NOT_PRICEABLE when the product is unpublished."""
    product = replace(demo_product(), is_published=False)

    quotation = price_product_for_customer(
        product=product,
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={},
    )

    assert quotation == Quotation(verdict=PricingVerdict.NOT_PRICEABLE, total=None, breakdown=())


def test_a_customer_choice_that_makes_a_parent_present_requires_its_child() -> None:
    """A selected present parent makes its undeclared dependent attribute required."""
    quotation = price_product_for_customer(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={BACKLIGHT: ConfiguredValue(value_id=CONTOUR, quantity=None)},
    )

    assert quotation == Quotation(verdict=PricingVerdict.NOT_PRICEABLE, total=None, breakdown=())


@pytest.mark.parametrize("child_value", [NO_HEATING, WITH_HEATING])
def test_an_absent_selected_parent_removes_its_child_from_the_price(child_value: AttributeValueId) -> None:
    """A child contributes nothing after the customer makes its parent absent."""
    product = demo_product_with_value(BACKLIGHT, CONTOUR)
    product = product_with_added_declaration(
        product,
        DeclaredValue(
            attribute_id=HEATING,
            configured=ConfiguredValue(value_id=child_value, quantity=None),
        ),
    )

    quotation = price_product_for_customer(
        product=product,
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={BACKLIGHT: ConfiguredValue(value_id=NO_BACKLIGHT, quantity=None)},
    )

    assert quotation == canonical_quotation(PricingVerdict.PRICED)


def test_a_customer_choice_cannot_complete_an_unfinished_owner_declaration() -> None:
    """An unfinished owner declaration remains NOT_PRICEABLE after a customer choice."""
    product = demo_product_with_value(BLADE, None)

    quotation = price_product_for_customer(
        product=product,
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={BLADE: ConfiguredValue(value_id=SILVER, quantity=None)},
    )

    assert quotation == Quotation(verdict=PricingVerdict.NOT_PRICEABLE, total=None, breakdown=())


def test_a_zero_numeric_quantity_is_complete_and_consumed_exactly() -> None:
    """Decimal zero is a configured numeric quantity, not a missing declaration."""
    pricing_settings = replace(demo_settings(), min_order_total=Money(amount=Decimal(0)))

    quotation = price_product_for_customer(
        product=demo_numeric_product(quantity=Decimal(0)),
        attributes=[demo_cutouts()],
        settings=pricing_settings,
        dimensions=_dimensions(800, 600),
        selections={},
    )

    assert quotation == Quotation(
        verdict=PricingVerdict.PRICED,
        total=Money(amount=Decimal(0)),
        breakdown=(quotation_line(CUTOUTS, CUTOUT, "0", ("100", Unit.PIECE, "0")),),
    )


def test_a_customer_cannot_select_a_non_changeable_attribute() -> None:
    """A choice on a non-changeable attribute receives NOT_PRICEABLE."""
    attributes = demo_attributes_with_changeability(FRAME, is_customer_changeable=False)

    quotation = price_product_for_customer(
        product=demo_product(),
        attributes=attributes,
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={FRAME: ConfiguredValue(value_id=NO_FRAME, quantity=None)},
    )

    assert quotation == Quotation(verdict=PricingVerdict.NOT_PRICEABLE, total=None, breakdown=())


def test_a_customer_beyond_production_limits_receives_that_verdict() -> None:
    """A customer size beyond a production bound receives BEYOND_LIMITS."""
    pricing_settings = replace(
        demo_settings(),
        max_long_side_mm=Millimeters(value=700),
        max_short_side_mm=Millimeters(value=500),
    )

    quotation = price_product_for_customer(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=pricing_settings,
        dimensions=_dimensions(800, 600),
        selections={},
    )

    assert quotation == Quotation(verdict=PricingVerdict.BEYOND_LIMITS, total=None, breakdown=())


def test_a_hidden_customer_price_is_calculated_but_marked_hidden() -> None:
    """A hidden price completes the arithmetic and carries HIDDEN instead of PRICED."""
    product = replace(demo_product(), hides_calculated_price=True)

    quotation = price_product_for_customer(
        product=product,
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={},
    )

    assert quotation == canonical_quotation(PricingVerdict.HIDDEN)


def test_a_fractional_numeric_selection_is_charged_as_its_exact_quantity() -> None:
    """A numeric customer selection consumes exactly Decimal('2.5') from its sole dictionary row."""
    pricing_settings = replace(demo_settings(), min_order_total=Money(amount=Decimal(0)))

    quotation = price_product_for_customer(
        product=demo_numeric_product(quantity=Decimal(1)),
        attributes=[demo_cutouts()],
        settings=pricing_settings,
        dimensions=_dimensions(800, 600),
        selections={CUTOUTS: ConfiguredValue(value_id=None, quantity=Decimal("2.5"))},
    )

    assert quotation == Quotation(
        verdict=PricingVerdict.PRICED,
        total=Money(amount=Decimal(300)),
        breakdown=(quotation_line(CUTOUTS, CUTOUT, "2.5", ("100", Unit.PIECE, "250")),),
    )


@pytest.mark.parametrize("_example_group", range(40))
@settings(max_examples=25)
@given(case=rotated_limit_cases())
def test_one_thousand_limit_decisions_are_rotation_invariant(
    _example_group: int,
    case: tuple[Dimensions, Millimeters, Millimeters, PricingVerdict],
) -> None:
    """One thousand rotated or unrotated sizes receive the expected production verdict."""
    size, long_limit, short_limit, expected_verdict = case
    pricing_settings = replace(
        demo_settings(),
        max_long_side_mm=long_limit,
        max_short_side_mm=short_limit,
    )

    quotation = price_product_for_customer(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=pricing_settings,
        dimensions=size,
        selections={},
    )

    assert quotation.verdict is expected_verdict


@pytest.mark.parametrize("_example_group", range(40))
@settings(max_examples=25)
@given(case=customer_gate_cases())
def test_one_thousand_customer_verdicts_keep_their_total_and_emptiness_invariants(
    _example_group: int,
    case: tuple[Product, PricingSettings, Dimensions, PricingVerdict, bool],
) -> None:
    """One thousand coherent customer questions keep every verdict's quotation shape."""
    product, pricing_settings, size, expected_verdict, carries_price = case

    quotation = price_product_for_customer(
        product=product,
        attributes=demo_attributes(),
        settings=pricing_settings,
        dimensions=size,
        selections={},
    )

    assert quotation.verdict is expected_verdict
    assert (quotation.total is not None) is carries_price
    assert bool(quotation.breakdown) is carries_price


@pytest.mark.parametrize("_example_group", range(40))
@settings(max_examples=25)
@given(quantity=fractional_quantities())
def test_one_thousand_fractional_numeric_prices_keep_exact_consumption(
    _example_group: int,
    quantity: Decimal,
) -> None:
    """One thousand generated numeric prices retain every fractional Decimal exactly."""
    pricing_settings = replace(demo_settings(), min_order_total=Money(amount=Decimal(0)))

    quotation = price_product_for_customer(
        product=demo_numeric_product(quantity=Decimal(1)),
        attributes=[demo_cutouts()],
        settings=pricing_settings,
        dimensions=_dimensions(800, 600),
        selections={CUTOUTS: ConfiguredValue(value_id=None, quantity=quantity)},
    )

    assert quotation.breakdown[0].quantity == quantity
