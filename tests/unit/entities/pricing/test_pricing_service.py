from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given, settings

from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.catalog.product.entity import ConfiguredValue, DeclaredValue, Product
from memiro.entities.common.identifiers import AttributeId, AttributeValueId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.pricing.pricing_service import (
    ROUNDING_STEP,
    is_product_priceable,
    price_product,
    price_product_for_customer,
    selection_deltas,
)
from memiro.entities.pricing.pricing_settings import PricingSettings
from memiro.entities.pricing.quotation import PricingVerdict, Quotation, QuotationLine
from tests.common.factory.catalog import (
    ALUMINIUM,
    BACKLIGHT,
    BLADE,
    CONTOUR,
    CUTOUT,
    CUTOUTS,
    FRAME,
    GRAPHITE,
    HEATING,
    MOUNT,
    NO_BACKLIGHT,
    NO_FRAME,
    NO_HEATING,
    NO_MOUNT,
    RECTANGULAR,
    ROUND,
    SHAPE,
    SILVER,
    WITH_HEATING,
    WITH_MOUNT,
    demo_attributes,
    demo_backlight,
    demo_cutouts,
    demo_defaults,
    demo_frame,
    demo_heating,
    demo_numeric_product,
    demo_product,
    demo_settings,
    demo_shape,
)
from tests.unit.composite import (
    complete_products,
    configurations,
    customer_gate_case_batches,
    dimensions,
    fractional_quantity_batches,
    incomplete_products,
    pricing_case_batches,
    rotated_limit_case_batches,
)


def _dimensions(width: int, height: int) -> Dimensions:
    return Dimensions(width=Millimeters(value=width), height=Millimeters(value=height))


def _expected_line(
    attribute_id: AttributeId,
    value_id: AttributeValueId,
    quantity: str,
    price: tuple[str, Unit, str],
) -> QuotationLine:
    rate, unit, amount = price
    return QuotationLine(
        attribute_id=attribute_id,
        value_id=value_id,
        quantity=Decimal(quantity),
        rate=Rate(amount=Money(amount=Decimal(rate)), unit=unit),
        amount=Money(amount=Decimal(amount)),
    )


def _canonical_quotation(verdict: PricingVerdict) -> Quotation:
    """Build the hand-checked workbook result without calling pricing logic."""
    return Quotation(
        verdict=verdict,
        total=Money(amount=Decimal(8900)),
        breakdown=(
            _expected_line(BLADE, SILVER, "0.48", ("4500", Unit.SQUARE_METER, "2160")),
            _expected_line(FRAME, ALUMINIUM, "2.8", ("2200", Unit.LINEAR_METER, "6160")),
            _expected_line(MOUNT, WITH_MOUNT, "1", ("500", Unit.PIECE, "500")),
        ),
    )


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


def test_a_product_missing_an_applicable_declaration_is_not_priceable() -> None:
    """A root attribute without a product declaration makes the product not priceable."""
    product = demo_product()
    product = replace(
        product,
        declared_values=[declaration for declaration in product.declared_values if declaration.attribute_id != MOUNT],
    )

    assert not is_product_priceable(product, demo_attributes())


def test_an_absent_parent_makes_its_undeclared_child_inapplicable() -> None:
    """An absence-marked parent lets its undeclared dependent attribute stay inapplicable."""
    assert is_product_priceable(demo_product(), demo_attributes())


def test_a_present_parent_makes_its_child_declaration_required() -> None:
    """A present parent makes an undeclared dependent attribute required for pricing."""
    product = demo_product()
    product = replace(
        product,
        declared_values=[
            replace(declaration, value_id=CONTOUR) if declaration.attribute_id == BACKLIGHT else declaration
            for declaration in product.declared_values
        ],
    )

    assert not is_product_priceable(product, demo_attributes())


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


def test_a_customer_choice_that_makes_a_parent_absent_ignores_its_child() -> None:
    """A selected absent parent makes its complete dependent attribute irrelevant."""
    product = demo_product()
    product = replace(
        product,
        declared_values=[
            replace(declaration, value_id=CONTOUR) if declaration.attribute_id == BACKLIGHT else declaration
            for declaration in product.declared_values
        ]
        + [DeclaredValue(attribute_id=HEATING, value_id=NO_HEATING)],
    )

    quotation = price_product_for_customer(
        product=product,
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={BACKLIGHT: ConfiguredValue(value_id=NO_BACKLIGHT, quantity=None)},
    )

    assert quotation == _canonical_quotation(PricingVerdict.PRICED)


def test_an_absent_selected_parent_removes_its_paid_child_from_the_price() -> None:
    """A paid child contributes nothing after the customer makes its parent absent."""
    product = demo_product()
    product = replace(
        product,
        declared_values=[
            replace(declaration, value_id=CONTOUR) if declaration.attribute_id == BACKLIGHT else declaration
            for declaration in product.declared_values
        ]
        + [DeclaredValue(attribute_id=HEATING, value_id=WITH_HEATING)],
    )

    quotation = price_product_for_customer(
        product=product,
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={BACKLIGHT: ConfiguredValue(value_id=NO_BACKLIGHT, quantity=None)},
    )

    assert quotation == _canonical_quotation(PricingVerdict.PRICED)


def test_a_customer_choice_cannot_complete_an_unfinished_owner_declaration() -> None:
    """An unfinished owner declaration remains NOT_PRICEABLE after a customer choice."""
    product = demo_product()
    product = replace(
        product,
        declared_values=[
            replace(declaration, value_id=None) if declaration.attribute_id == BLADE else declaration
            for declaration in product.declared_values
        ],
    )

    quotation = price_product_for_customer(
        product=product,
        attributes=demo_attributes(),
        settings=demo_settings(),
        dimensions=_dimensions(800, 600),
        selections={BLADE: ConfiguredValue(value_id=SILVER, quantity=None)},
    )

    assert quotation == Quotation(verdict=PricingVerdict.NOT_PRICEABLE, total=None, breakdown=())


def test_a_product_without_a_paid_declaration_is_not_priceable() -> None:
    """A complete product made only of a free absence value is not priceable."""
    product = replace(
        demo_product(),
        declared_values=[DeclaredValue(attribute_id=FRAME, value_id=NO_FRAME)],
    )

    assert not is_product_priceable(product, [demo_frame()])


def test_a_free_present_parent_still_makes_its_child_required() -> None:
    """A zero tariff does not make a present parent value mean absence."""
    backlight = demo_backlight()
    backlight = replace(
        backlight,
        values=[backlight.values[0], replace(backlight.values[1], marks_absence=False)],
    )
    attributes = demo_attributes()
    attributes[3] = backlight

    assert not is_product_priceable(demo_product(), attributes)


def test_a_factor_without_a_money_line_does_not_make_a_product_priceable() -> None:
    """A shape factor alone cannot satisfy the paid-declaration rule."""
    product = replace(
        demo_product(),
        declared_values=[DeclaredValue(attribute_id=SHAPE, value_id=RECTANGULAR)],
    )

    assert not is_product_priceable(product, [demo_shape()])


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
        breakdown=(_expected_line(CUTOUTS, CUTOUT, "0", ("100", Unit.PIECE, "0")),),
    )


def test_attributes_of_another_category_do_not_make_a_product_incomplete() -> None:
    """Priceability considers only attributes belonging to the product category."""
    foreign = replace(demo_frame(), id=uuid4(), category_id=uuid4())

    assert is_product_priceable(demo_product(), [*demo_attributes(), foreign])


def test_a_missing_parent_is_reported_as_a_dictionary_defect() -> None:
    """A missing parent raises an English RuntimeError instead of leaking a KeyError."""
    child = replace(demo_heating(), parent_ids=(uuid4(),))
    attributes = demo_attributes()
    attributes[5] = child

    with pytest.raises(
        RuntimeError,
        match=r"Parent attribute .* is missing or outside product category",
    ):
        is_product_priceable(demo_product(), attributes)


def test_a_parent_from_another_category_is_reported_as_a_dictionary_defect() -> None:
    """A foreign-category parent raises an English RuntimeError as corrupted dictionary state."""
    foreign_parent = replace(demo_backlight(), category_id=uuid4())
    attributes = demo_attributes()
    attributes[3] = foreign_parent

    with pytest.raises(
        RuntimeError,
        match=r"Parent attribute .* is missing or outside product category",
    ):
        is_product_priceable(demo_product(), attributes)


def test_a_customer_cannot_select_a_non_changeable_attribute() -> None:
    """A choice on a non-changeable attribute receives NOT_PRICEABLE."""
    attributes: list[Attribute] = [
        replace(attribute, is_customer_changeable=False) if attribute.id == FRAME else attribute
        for attribute in demo_attributes()
    ]

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
    settings = replace(
        demo_settings(),
        max_long_side_mm=Millimeters(value=700),
        max_short_side_mm=Millimeters(value=500),
    )

    quotation = price_product_for_customer(
        product=demo_product(),
        attributes=demo_attributes(),
        settings=settings,
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

    assert quotation == _canonical_quotation(PricingVerdict.HIDDEN)


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

    assert quotation == _canonical_quotation(PricingVerdict.PRICED)


def test_the_owner_prices_a_product_without_a_paid_default() -> None:
    """The owner's calculation does not apply the customer's paid-value gate."""
    product = replace(
        demo_product(),
        declared_values=[DeclaredValue(attribute_id=FRAME, value_id=NO_FRAME)],
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
    attributes = [
        replace(attribute, is_customer_changeable=False) if attribute.id == FRAME else attribute
        for attribute in demo_attributes()
    ]

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
            _expected_line(BLADE, SILVER, "0.48", ("4500", Unit.SQUARE_METER, "2160")),
            _expected_line(MOUNT, WITH_MOUNT, "1", ("500", Unit.PIECE, "500")),
        ),
    )


def test_a_fractional_numeric_selection_is_charged_as_its_exact_quantity() -> None:
    """A numeric customer selection consumes exactly Decimal('2.5') from its sole dictionary row."""
    pricing_settings = replace(
        demo_settings(),
        min_order_total=Money(amount=Decimal(0)),
    )

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
        breakdown=(_expected_line(CUTOUTS, CUTOUT, "2.5", ("100", Unit.PIECE, "250")),),
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


@settings(max_examples=25)
@given(cases=pricing_case_batches())
def test_one_thousand_prices_are_whole_hundreds_at_or_above_the_minimum_order(
    cases: tuple[tuple[Dimensions, dict[AttributeId, AttributeValueId]], ...],
) -> None:
    """One thousand coherent configurations preserve rounding and the minimum order."""
    quotations = tuple(
        price_product(
            product=demo_product(),
            attributes=demo_attributes(),
            settings=demo_settings(),
            dimensions=size,
            selections=selections,
        )
        for size, selections in cases
    )

    assert all(quotation.total is not None for quotation in quotations)
    assert all(
        quotation.total is not None and quotation.total.amount % ROUNDING_STEP == Decimal(0) for quotation in quotations
    )
    # The threshold is the owner's datum, so it is read from the same fixture
    # the calculation was given — the second place to fix is demo_settings().
    assert all(
        quotation.total is not None and quotation.total >= demo_settings().min_order_total for quotation in quotations
    )


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

    assert {line.rate.unit for line in quotation.breakdown} <= {Unit.SQUARE_METER, Unit.LINEAR_METER, Unit.PIECE}
    assert {line.rate.is_free() for line in quotation.breakdown} <= {False}


@settings(max_examples=25)
@given(cases=rotated_limit_case_batches())
def test_one_thousand_limit_decisions_are_rotation_invariant(
    cases: tuple[tuple[Dimensions, Dimensions, Millimeters, Millimeters, PricingVerdict], ...],
) -> None:
    """One thousand finite or unlimited bounds give both rotations the expected verdict."""
    quotations = tuple(
        (
            price_product_for_customer(
                product=demo_product(),
                attributes=demo_attributes(),
                settings=replace(
                    demo_settings(),
                    max_long_side_mm=long_limit,
                    max_short_side_mm=short_limit,
                ),
                dimensions=first,
                selections={},
            ),
            price_product_for_customer(
                product=demo_product(),
                attributes=demo_attributes(),
                settings=replace(
                    demo_settings(),
                    max_long_side_mm=long_limit,
                    max_short_side_mm=short_limit,
                ),
                dimensions=rotated,
                selections={},
            ),
            verdict,
        )
        for first, rotated, long_limit, short_limit, verdict in cases
    )

    assert {(first.verdict, rotated.verdict, expected) for first, rotated, expected in quotations} <= {
        (PricingVerdict.PRICED, PricingVerdict.PRICED, PricingVerdict.PRICED),
        (PricingVerdict.BEYOND_LIMITS, PricingVerdict.BEYOND_LIMITS, PricingVerdict.BEYOND_LIMITS),
    }
    assert {first.total == rotated.total for first, rotated, _ in quotations} == {True}


@settings(max_examples=25)
@given(cases=customer_gate_case_batches())
def test_one_thousand_customer_verdicts_keep_their_total_and_emptiness_invariants(
    cases: tuple[tuple[Product, PricingSettings, Dimensions, PricingVerdict], ...],
) -> None:
    """One thousand coherent customer questions keep every verdict's quotation shape."""
    quotations = tuple(
        (
            price_product_for_customer(
                product=product,
                attributes=demo_attributes(),
                settings=pricing_settings,
                dimensions=size,
                selections={},
            ),
            verdict,
        )
        for product, pricing_settings, size, verdict in cases
    )

    assert {quotation.verdict is verdict for quotation, verdict in quotations} == {True}
    assert {
        (quotation.total is not None) is (verdict in {PricingVerdict.PRICED, PricingVerdict.HIDDEN})
        for quotation, verdict in quotations
    } == {True}
    assert {
        bool(quotation.breakdown) is (verdict in {PricingVerdict.PRICED, PricingVerdict.HIDDEN})
        for quotation, verdict in quotations
    } == {True}


@settings(max_examples=25)
@given(product=complete_products())
def test_every_coherently_complete_product_is_priceable(product: Product) -> None:
    """A complete set stays priceable whether an absent dependency stays off or is filled."""
    assert is_product_priceable(product, demo_attributes())


@settings(max_examples=25)
@given(product=incomplete_products())
def test_every_coherent_declaration_gap_makes_a_product_not_priceable(product: Product) -> None:
    """Missing any required root or newly applicable child always makes the product not priceable."""
    assert not is_product_priceable(product, demo_attributes())


@settings(max_examples=25)
@given(quantities=fractional_quantity_batches())
def test_fractional_numeric_consumption_stays_exact_across_a_dense_batch(
    quantities: tuple[Decimal, ...],
) -> None:
    """One thousand generated numeric prices retain every fractional Decimal exactly."""
    pricing_settings = replace(demo_settings(), min_order_total=Money(amount=Decimal(0)))

    quotations = [
        price_product_for_customer(
            product=demo_numeric_product(quantity=Decimal(1)),
            attributes=[demo_cutouts()],
            settings=pricing_settings,
            dimensions=_dimensions(800, 600),
            selections={CUTOUTS: ConfiguredValue(value_id=None, quantity=quantity)},
        )
        for quantity in quantities
    ]

    assert tuple(quotation.breakdown[0].quantity for quotation in quotations) == quantities
