from dataclasses import replace
from decimal import Decimal

import pytest
from hypothesis import given, settings

from memiro.entities.catalog.attribute.rate import Unit
from memiro.entities.catalog.product.entity import ConfiguredValue, DeclaredValue
from memiro.entities.common.identifiers import AttributeId, AttributeValueId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.pricing.pricing_service import (
    ROUNDING_STEP,
    price_product,
    selection_deltas,
)
from memiro.entities.pricing.quotation import PricingVerdict, Quotation, QuotationLine
from tests.common.factory.catalog import (
    ALUMINIUM,
    BACKLIGHT,
    BLADE,
    CONTOUR,
    FRAME,
    GRAPHITE,
    MOUNT,
    NO_BACKLIGHT,
    NO_FRAME,
    NO_MOUNT,
    ROUND,
    SHAPE,
    SILVER,
    WITH_MOUNT,
    demo_attributes,
    demo_attributes_with_changeability,
    demo_defaults,
    demo_frame,
    demo_product,
    demo_settings,
)
from tests.common.pricing_expected import canonical_quotation, quotation_line
from tests.unit.composite import (
    configurations,
    dimensions,
    pricing_cases,
)


def _dimensions(width: int, height: int) -> Dimensions:
    return Dimensions(width=Millimeters(value=width), height=Millimeters(value=height))


def _line_units(lines: tuple[QuotationLine, ...]) -> set[Unit]:
    return {line.rate.unit for line in lines}


def _line_free_states(lines: tuple[QuotationLine, ...]) -> set[bool]:
    return {line.rate.is_free() for line in lines}


def test_the_owner_prices_without_customer_gates() -> None:
    """The owner receives the arithmetic despite publication, hiding and production limits."""
    product = replace(demo_product(), is_published=False, hides_calculated_price=True)
    settings = replace(
        demo_settings(),
        max_long_side_mm=Millimeters(value=1),
        max_short_side_mm=Millimeters(value=1),
    )

    quotation = price_product(
        product=product,
        attributes=demo_attributes(),
        settings=settings,
        dimensions=_dimensions(800, 600),
        selections={},
    )

    assert quotation == canonical_quotation(PricingVerdict.PRICED)


def test_the_owner_prices_a_product_without_a_paid_default() -> None:
    """The owner's calculation does not apply the customer's paid-value gate."""
    product = replace(
        demo_product(),
        declared_values=[
            DeclaredValue(
                attribute_id=FRAME,
                configured=ConfiguredValue(value_id=NO_FRAME, quantity=None),
            )
        ],
    )

    quotation = price_product(
        product=product,
        attributes=[demo_frame()],
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={},
    )

    assert quotation == Quotation(
        verdict=PricingVerdict.PRICED,
        total=Money(amount=Decimal(2000)),
        breakdown=(),
    )


def test_the_owner_changes_an_attribute_reserved_for_the_owner() -> None:
    """The owner's calculation does not apply the customer's changeability gate."""
    attributes = demo_attributes_with_changeability(FRAME, is_customer_changeable=False)

    quotation = price_product(
        product=demo_product(),
        attributes=attributes,
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={FRAME: NO_FRAME},
    )

    assert quotation == Quotation(
        verdict=PricingVerdict.PRICED,
        total=Money(amount=Decimal(2700)),
        breakdown=(
            quotation_line(BLADE, SILVER, "0.48", ("4500", Unit.SQUARE_METER, "2160")),
            quotation_line(MOUNT, WITH_MOUNT, "1", ("500", Unit.PIECE, "500")),
        ),
    )


def test_a_mirror_in_a_frame_costs_what_the_workbook_says() -> None:
    """The canonical case of the xlsx workbook: 800 x 600 in an aluminium frame is 8 900 RUB."""
    quotation = price_product(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={},
    )

    # 0.48 m2 x 4500 + 2.8 lm x 2200 + 500 = 8 820, rounded up to whole hundreds.
    # The same numbers live in docs/usecase/calculate_price/calculate-price.md.
    assert quotation.total == Money(amount=Decimal(8900))
    assert quotation.verdict is PricingVerdict.PRICED


def test_a_curved_cut_multiplies_the_blade_but_not_the_backlight() -> None:
    """A round mirror pays the shape factor on the blade only: 900 x 900 with a tape is 15 000 RUB."""
    quotation = price_product(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(900, 900),
        selections={SHAPE: ROUND, FRAME: NO_FRAME, BACKLIGHT: CONTOUR},
    )

    # 0.81 m2 x 4500 x 1.5 = 5 467.50 for the blade, 3.6 lm x 2500 = 9 000 for
    # the tape untouched by the factor, 500 for the mount: 14 967.50 -> 15 000.
    assert quotation.total == Money(amount=Decimal(15000))


def test_a_small_mirror_is_priced_by_the_minimum_area_and_the_minimum_order() -> None:
    """Both lower bounds bite: 400 x 300 with no frame and no mount is the 2 000 RUB minimum order."""
    quotation = price_product(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(400, 300),
        selections={FRAME: NO_FRAME, MOUNT: NO_MOUNT},
    )

    # 0.12 m2 is billed as 0.25 m2 x 4500 = 1 125, raised to the minimum order.
    assert quotation.total == Money(amount=Decimal(2000))


def test_a_free_value_gives_no_line_of_its_own() -> None:
    """A value with no tariff describes the mirror without costing anything, so it charges nothing."""
    quotation = price_product(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={},
    )

    assert [line.value_id for line in quotation.breakdown] == [SILVER, ALUMINIUM, WITH_MOUNT]


def test_every_value_is_charged_in_the_unit_it_is_consumed_in() -> None:
    """The blade goes by area, the frame by perimeter and the mount by the piece."""
    quotation = price_product(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={},
    )

    assert [line.quantity for line in quotation.breakdown] == [
        Decimal("0.48"),
        Decimal("2.8"),
        Decimal(1),
    ]


def test_choosing_a_darker_blade_costs_the_difference_with_the_default() -> None:
    """Graphite instead of silver is charged as the difference of the two tariffs, not as a whole line."""
    deltas = selection_deltas(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={BLADE: GRAPHITE},
    )

    # (7000 - 4500) x 0.48 m2 = 1 200.
    assert deltas == {BLADE: Decimal(1200)}


def test_choosing_a_cheaper_blade_gives_a_negative_delta() -> None:
    """A blade cheaper than the product's default is a discount from the shown price, and it is shown."""
    deltas = selection_deltas(
        product=demo_product(blade=GRAPHITE),
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={BLADE: SILVER},
    )

    assert deltas == {BLADE: Decimal(-1200)}


def test_keeping_the_products_own_default_costs_nothing() -> None:
    """Choosing what the product already declares changes no line and no price."""
    deltas = selection_deltas(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={BACKLIGHT: NO_BACKLIGHT},
    )

    assert deltas == {BACKLIGHT: Decimal(0)}


def test_a_delta_is_taken_before_the_minimum_order_threshold() -> None:
    """On a mirror resting on the threshold the choice still costs its exact difference."""
    deltas = selection_deltas(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(400, 300),
        selections={BLADE: GRAPHITE, FRAME: NO_FRAME, MOUNT: NO_MOUNT},
    )

    # Both configurations are lifted to 2 000 RUB, yet graphite really costs
    # (7000 - 4500) x 0.25 m2 = 625 more.
    assert deltas[BLADE] == Decimal(625)


@pytest.mark.parametrize("_example_group", range(40))
@settings(max_examples=25)
@given(case=pricing_cases())
def test_one_thousand_prices_are_whole_hundreds_at_or_above_the_minimum_order(
    _example_group: int,
    case: tuple[Dimensions, dict[AttributeId, AttributeValueId]],
) -> None:
    """One thousand coherent configurations preserve rounding and the minimum order."""
    size, selections = case

    quotation = price_product(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=size,
        selections=selections,
    )

    assert quotation.total is not None
    assert quotation.total.amount % ROUNDING_STEP == Decimal(0)
    # The threshold is the owner's datum, so it is read from the same fixture
    # the calculation was given — the second place to fix is demo_settings().
    assert quotation.total >= demo_settings().min_order_total


@settings(max_examples=25)
@given(size=dimensions())
def test_keeping_every_default_of_the_product_costs_nothing_on_any_size(size: Dimensions) -> None:
    """Choosing exactly what the product declares moves no price, whatever the mirror measures."""
    defaults = demo_defaults()

    deltas = selection_deltas(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=size,
        selections=defaults,
    )

    assert deltas == dict.fromkeys(defaults, Decimal(0))


@settings(max_examples=25)
@given(size=dimensions(), selections=configurations())
def test_only_a_value_charged_per_unit_ever_becomes_a_line(
    size: Dimensions,
    selections: dict[AttributeId, AttributeValueId],
) -> None:
    """A free value and a shape factor describe the mirror without a line of their own.

    The units are the three the calculation knows how to consume; ``FACTOR``
    and a zero tariff are absent from both sets by the rule under test.
    """
    quotation = price_product(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=size,
        selections=selections,
    )

    assert _line_units(quotation.breakdown) <= {
        Unit.SQUARE_METER,
        Unit.LINEAR_METER,
        Unit.PIECE,
    }
    assert _line_free_states(quotation.breakdown) <= {False}
