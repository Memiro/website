from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.calculate_price import (
    CalculatedPrice,
    CalculatePriceForm,
    SelectionDelta,
)
from memiro.application.common.customer_selection import Selection
from memiro.application.common.input_limits import MAX_SELECTIONS, MAX_SIDE_MM
from memiro.entities.common.measure import Millimeters
from memiro.entities.pricing.quotation import PricingVerdict
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
    NO_MOUNT,
    PRODUCT,
    ROUND,
    SHAPE,
    SILVER,
    WITH_HEATING,
)
from tests.common.factory.pricing import SelectionFactory
from tests.integration.api_client import ApiClient
from tests.integration.prime import (
    corrupt_a_declaration_directly,
    prime_complete_heating_declaration,
    prime_hidden_calculated_price,
    prime_incomplete_declaration,
    prime_non_changeable_attribute,
    prime_numeric_catalog,
    prime_paid_heating_declaration,
    prime_present_dependency,
    prime_product_publication,
    prime_product_without_paid_values,
    prime_production_limits,
    prime_size_surcharge,
)

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


async def test_a_mirror_costs_more_from_the_first_size_surcharge_threshold(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """The public calculation steps up at 2200 mm and names that threshold without its factor."""
    await prime_size_surcharge(engine)

    below_response = await api_client.calculate(_form(width_mm=2199, height_mm=600))
    at_response = await api_client.calculate(_form(width_mm=2200, height_mm=600))

    below = below_response.assert_status(200).ensure_content()
    at = at_response.assert_status(200).ensure_content()
    assert below == CalculatedPrice(
        verdict=PricingVerdict.PRICED,
        total=Decimal(18800),
        selection_deltas=[],
    )
    assert at == CalculatedPrice(
        verdict=PricingVerdict.PRICED,
        total=Decimal(20300),
        selection_deltas=[],
        size_surcharge_from_long_side_mm=2200,
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


async def test_a_curved_cut_is_paid_by_the_blade_alone(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A round mirror with a tape answers 15 000 RUB: the factor takes the blade, not the backlight."""
    await prime_complete_heating_declaration(engine)
    round_mirror = [
        Selection(attribute_id=SHAPE, value_id=ROUND),
        Selection(attribute_id=FRAME, value_id=NO_FRAME),
        Selection(attribute_id=BACKLIGHT, value_id=CONTOUR),
    ]

    response = await api_client.calculate(_form(width_mm=900, height_mm=900, selections=round_mirror))

    # 0.81 m2 x 4500 x 1.5 + 3.6 lm x 2500 + 500 = 14 967.50 -> 15 000. The
    # round shape costs the blade its own 0.81 x 4500 x 0.5 = 1 822.50; the
    # frame and the tape the mirror gained or lost are their own lines.
    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.PRICED,
        total=Decimal(15000),
        selection_deltas=[
            SelectionDelta(attribute_id=SHAPE, value_id=ROUND, delta=Decimal("1822.500")),
            SelectionDelta(attribute_id=FRAME, value_id=NO_FRAME, delta=Decimal("-11880.00")),
            SelectionDelta(attribute_id=BACKLIGHT, value_id=CONTOUR, delta=Decimal("9000.000")),
        ],
    )


async def test_a_darker_blade_on_a_curved_cut_carries_the_factor(api_client: ApiClient) -> None:
    """Graphite on a round 900 x 900 mirror costs 3 037.50 RUB — the workbook's "+3 038 RUB"."""
    round_and_dark = [
        Selection(attribute_id=SHAPE, value_id=ROUND),
        Selection(attribute_id=BLADE, value_id=GRAPHITE),
    ]

    response = await api_client.calculate(_form(width_mm=900, height_mm=900, selections=round_and_dark))

    # (0.81 m2 x 7000 + 3.6 lm x 2200) x 1.5 + 500 = 20 885 -> 20 900. The
    # blade's own share is (7000 - 4500) x 0.81 m2 x 1.5 = 3 037.50: the choice
    # is priced inside the configuration the customer is looking at, curved cut
    # included. Dropping the round shape would leave 14 090, hence 6 795.
    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.PRICED,
        total=Decimal(20900),
        selection_deltas=[
            SelectionDelta(attribute_id=SHAPE, value_id=ROUND, delta=Decimal("6795.00")),
            SelectionDelta(attribute_id=BLADE, value_id=GRAPHITE, delta=Decimal("3037.50")),
        ],
    )


async def test_a_small_mirror_costs_the_minimum_order_and_the_choice_still_costs_its_own(
    api_client: ApiClient,
) -> None:
    """On a mirror resting on the 2 000 RUB threshold graphite still shows its exact 625 RUB."""
    bare_and_dark = [
        Selection(attribute_id=BLADE, value_id=GRAPHITE),
        Selection(attribute_id=FRAME, value_id=NO_FRAME),
        Selection(attribute_id=MOUNT, value_id=NO_MOUNT),
    ]

    response = await api_client.calculate(_form(width_mm=400, height_mm=300, selections=bare_and_dark))

    # 0.12 m2 is billed as the minimum 0.25 m2: 1 750 for the blade, lifted to
    # the minimum order; the blade itself is (7000 - 4500) x 0.25 = 625 dearer.
    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.PRICED,
        total=Decimal(2000),
        selection_deltas=[
            SelectionDelta(attribute_id=BLADE, value_id=GRAPHITE, delta=Decimal("625.00")),
            SelectionDelta(attribute_id=FRAME, value_id=NO_FRAME, delta=Decimal("-3080.00")),
            SelectionDelta(attribute_id=MOUNT, value_id=NO_MOUNT, delta=Decimal(-500)),
        ],
    )


async def test_an_absence_marked_parent_leaves_its_undeclared_child_out_of_pricing(
    api_client: ApiClient,
) -> None:
    """A missing dependent declaration is irrelevant while its parent explicitly marks absence."""
    response = await api_client.calculate(_form())

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.PRICED,
        total=Decimal(8900),
        selection_deltas=[],
    )


async def test_a_customer_choice_that_makes_a_parent_present_requires_its_child(
    api_client: ApiClient,
) -> None:
    """A selected present parent makes its undeclared child answer NOT_PRICEABLE."""
    selection = Selection(attribute_id=BACKLIGHT, value_id=CONTOUR)

    response = await api_client.calculate(_form(selections=[selection]))

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.NOT_PRICEABLE,
        total=None,
        selection_deltas=[],
    )


async def test_a_customer_choice_that_makes_a_parent_absent_ignores_its_child(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A selected absent parent makes its complete child irrelevant to pricing."""
    await prime_present_dependency(engine)
    await prime_complete_heating_declaration(engine)
    selection = Selection(attribute_id=BACKLIGHT, value_id=NO_BACKLIGHT)

    response = await api_client.calculate(_form(selections=[selection]))

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.PRICED,
        total=Decimal(8900),
        selection_deltas=[
            SelectionDelta(attribute_id=BACKLIGHT, value_id=NO_BACKLIGHT, delta=Decimal(-7000)),
        ],
    )


async def test_an_absent_selected_parent_removes_its_paid_child_from_the_price(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A paid child contributes nothing after the customer makes its parent absent."""
    await prime_paid_heating_declaration(engine)
    selection = Selection(attribute_id=BACKLIGHT, value_id=NO_BACKLIGHT)

    response = await api_client.calculate(_form(selections=[selection]))

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.PRICED,
        total=Decimal(8900),
        selection_deltas=[
            SelectionDelta(attribute_id=BACKLIGHT, value_id=NO_BACKLIGHT, delta=Decimal(-10500)),
        ],
    )


async def test_an_inapplicable_selected_child_is_absent_from_public_deltas(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A child disabled by another selection is absent from both the total and public deltas."""
    await prime_paid_heating_declaration(engine)
    selections = [
        Selection(attribute_id=BACKLIGHT, value_id=NO_BACKLIGHT),
        Selection(attribute_id=HEATING, value_id=WITH_HEATING),
    ]

    response = await api_client.calculate(_form(selections=selections))

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.PRICED,
        total=Decimal(8900),
        selection_deltas=[
            SelectionDelta(attribute_id=BACKLIGHT, value_id=NO_BACKLIGHT, delta=Decimal(-10500)),
        ],
    )


async def test_rotated_dimensions_use_the_long_and_short_production_limits(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A rotated 600 x 800 mirror fits production limits expressed as 800 x 600."""
    await prime_production_limits(
        engine,
        max_long_side_mm=Millimeters(value=800),
        max_short_side_mm=Millimeters(value=600),
    )

    response = await api_client.calculate(_form(width_mm=600, height_mm=800))

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.PRICED,
        total=Decimal(8900),
        selection_deltas=[],
    )


async def test_zero_production_limits_leave_both_sides_unlimited(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """Zero production bounds allow dimensions up to the independent request limit."""
    await prime_production_limits(
        engine,
        max_long_side_mm=Millimeters(value=0),
        max_short_side_mm=Millimeters(value=0),
    )

    response = await api_client.calculate(_form(width_mm=10_000, height_mm=9000))

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.PRICED,
        total=Decimal(489100),
        selection_deltas=[],
    )


async def test_a_fractional_numeric_quantity_is_priced_exactly(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A customer can replace one numeric unit with Decimal('2.5') without integer rounding."""
    await prime_numeric_catalog(engine)
    selection = Selection(attribute_id=CUTOUTS, quantity=Decimal("2.5"))

    response = await api_client.calculate(_form(selections=[selection]))

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.PRICED,
        total=Decimal(300),
        selection_deltas=[SelectionDelta(attribute_id=CUTOUTS, value_id=None, delta=Decimal(150))],
    )


async def test_an_unpublished_product_is_not_priceable(api_client: ApiClient, engine: AsyncEngine) -> None:
    """An unpublished product answers NOT_PRICEABLE without naming a total."""
    await prime_product_publication(engine, is_published=False)

    response = await api_client.calculate(_form())

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.NOT_PRICEABLE,
        total=None,
        selection_deltas=[],
    )


async def test_an_incomplete_applicable_declaration_is_not_priceable(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """An unfinished declaration answers NOT_PRICEABLE without naming a total."""
    await prime_incomplete_declaration(engine)

    response = await api_client.calculate(_form())

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.NOT_PRICEABLE,
        total=None,
        selection_deltas=[],
    )


async def test_a_customer_choice_cannot_complete_an_unfinished_owner_declaration(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """An unfinished owner declaration remains NOT_PRICEABLE after a customer choice."""
    await prime_incomplete_declaration(engine)
    selection = Selection(attribute_id=BLADE, value_id=SILVER)

    response = await api_client.calculate(_form(selections=[selection]))

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.NOT_PRICEABLE,
        total=None,
        selection_deltas=[],
    )


async def test_a_present_parent_makes_its_incomplete_child_not_priceable(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A present dependency parent makes the missing child declaration produce NOT_PRICEABLE."""
    await prime_present_dependency(engine)

    response = await api_client.calculate(_form())

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.NOT_PRICEABLE,
        total=None,
        selection_deltas=[],
    )


async def test_a_product_without_a_paid_value_is_not_priceable(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A complete configuration made only of free values answers NOT_PRICEABLE."""
    await prime_product_without_paid_values(engine)

    response = await api_client.calculate(_form())

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.NOT_PRICEABLE,
        total=None,
        selection_deltas=[],
    )


async def test_a_customer_choice_on_a_non_changeable_attribute_is_not_priceable(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A valid choice on an owner-only attribute answers NOT_PRICEABLE."""
    await prime_non_changeable_attribute(engine)
    selection = Selection(attribute_id=BLADE, value_id=GRAPHITE)

    response = await api_client.calculate(_form(selections=[selection]))

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.NOT_PRICEABLE,
        total=None,
        selection_deltas=[],
    )


async def test_a_customer_beyond_production_limits_receives_that_verdict(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A size over production's long and short bounds answers BEYOND_LIMITS."""
    await prime_production_limits(
        engine,
        max_long_side_mm=Millimeters(value=700),
        max_short_side_mm=Millimeters(value=500),
    )
    selection = Selection(attribute_id=BLADE, value_id=GRAPHITE)

    response = await api_client.calculate(_form(selections=[selection]))

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.BEYOND_LIMITS,
        total=None,
        selection_deltas=[],
    )


async def test_a_hidden_customer_price_exposes_neither_total_nor_deltas(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """HIDDEN completes pricing internally but its public projection carries no amounts."""
    await prime_hidden_calculated_price(engine)
    await prime_size_surcharge(engine)
    selection = Selection(attribute_id=BLADE, value_id=GRAPHITE)

    response = await api_client.calculate(_form(width_mm=2200, height_mm=600, selections=[selection]))

    assert response.assert_status(200).ensure_content() == CalculatedPrice(
        verdict=PricingVerdict.HIDDEN,
        total=None,
        selection_deltas=[],
        size_surcharge_from_long_side_mm=2200,
    )


async def test_the_answer_says_nothing_about_how_the_price_is_made(api_client: ApiClient) -> None:
    """The public projection carries no tariffs, no factors and no lines of blade and edge."""
    response = await api_client.calculate(_form())

    body = response.text
    assert "4500" not in body
    assert "2200" not in body
    assert "breakdown" not in body
    assert "rate" not in body


async def test_a_defect_in_the_data_answers_the_same_error_shape(api_client: ApiClient, engine: AsyncEngine) -> None:
    """A declaration pointing at another attribute's value answers 500 INTERNAL_ERROR, not a plain-text page."""
    await corrupt_a_declaration_directly(engine)

    response = await api_client.calculate(_form())

    response.assert_error(500, "INTERNAL_ERROR")


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


async def test_pricing_fails_if_a_select_attribute_is_supplied_as_a_quantity(api_client: ApiClient) -> None:
    """A quantity for a SELECT attribute is refused with ATTRIBUTE_VALUE_NOT_FOUND."""
    selection = Selection(attribute_id=BLADE, quantity=Decimal("2.5"))

    response = await api_client.calculate(_form(selections=[selection]))

    response.assert_error(404, "ATTRIBUTE_VALUE_NOT_FOUND")


async def test_pricing_fails_if_a_numeric_attribute_is_supplied_as_a_value(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A dictionary value for a NUMBER attribute is refused with ATTRIBUTE_VALUE_NOT_FOUND."""
    await prime_numeric_catalog(engine)
    selection = Selection(attribute_id=CUTOUTS, value_id=CUTOUT)

    response = await api_client.calculate(_form(selections=[selection]))

    response.assert_error(404, "ATTRIBUTE_VALUE_NOT_FOUND")


async def test_selection_identity_is_validated_before_the_publication_gate(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """An unknown value on an unpublished product is still refused with ATTRIBUTE_VALUE_NOT_FOUND."""
    await prime_product_publication(engine, is_published=False)
    selection = Selection(attribute_id=BLADE, value_id=uuid4())

    response = await api_client.calculate(_form(selections=[selection]))

    response.assert_error(404, "ATTRIBUTE_VALUE_NOT_FOUND")


async def test_pricing_fails_if_the_attribute_is_not_declared_by_the_product(api_client: ApiClient) -> None:
    """Heating the mirror never had is refused with ATTRIBUTE_VALUE_NOT_FOUND: there is nothing to replace."""
    selection = Selection(attribute_id=HEATING, value_id=WITH_HEATING)

    response = await api_client.calculate(_form(selections=[selection]))

    response.assert_error(404, "ATTRIBUTE_VALUE_NOT_FOUND")


async def test_pricing_fails_if_one_attribute_is_chosen_twice(api_client: ApiClient) -> None:
    """Two values of one attribute are refused with VALIDATION_ERROR: only one of them could be priced."""
    twice = [
        Selection(attribute_id=BLADE, value_id=GRAPHITE),
        Selection(attribute_id=BLADE, value_id=SILVER),
    ]
    dishonest = CalculatePriceForm.model_construct(
        product_id=PRODUCT,
        width_mm=800,
        height_mm=600,
        selections=twice,
    )

    response = await api_client.calculate(dishonest)

    response.assert_error(422, "VALIDATION_ERROR")


async def test_pricing_fails_if_a_selection_names_both_a_value_and_a_quantity(api_client: ApiClient) -> None:
    """A selection with two representations is refused with VALIDATION_ERROR."""
    dishonest_selection = Selection.model_construct(
        attribute_id=BLADE,
        value_id=GRAPHITE,
        quantity=Decimal("2.5"),
    )
    dishonest = _form(selections=[dishonest_selection])

    response = await api_client.calculate(dishonest)

    response.assert_error(422, "VALIDATION_ERROR")


async def test_pricing_fails_if_a_selection_names_neither_a_value_nor_a_quantity(api_client: ApiClient) -> None:
    """A selection with no representation is refused with VALIDATION_ERROR."""
    dishonest_selection = Selection.model_construct(attribute_id=BLADE)
    dishonest = _form(selections=[dishonest_selection])

    response = await api_client.calculate(dishonest)

    response.assert_error(422, "VALIDATION_ERROR")


async def test_pricing_fails_if_there_is_one_selection_too_many(api_client: ApiClient) -> None:
    """One choice over the form's bound is refused with VALIDATION_ERROR."""
    dishonest = CalculatePriceForm.model_construct(
        product_id=PRODUCT,
        width_mm=800,
        height_mm=600,
        selections=SelectionFactory.batch(MAX_SELECTIONS + 1),
    )

    response = await api_client.calculate(dishonest)

    response.assert_error(422, "VALIDATION_ERROR")


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
