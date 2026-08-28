"""Hypothesis strategies of the unit level — the one home for every ``@st.composite``.

The draws are coherent by construction: a configuration is assembled out of
the demo dictionary the way the owner assembles one, so no test has to patch a
drawn value into legality afterwards (§14.7.2).
"""

from dataclasses import replace
from decimal import Decimal

from hypothesis import strategies as st

from memiro.application.common.input_limits import MAX_SIDE_MM, MIN_SIDE_MM
from memiro.entities.catalog.product.entity import ConfiguredValue, DeclaredValue, Product
from memiro.entities.common.identifiers import AttributeId, AttributeValueId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.pricing.pricing_settings import PricingSettings
from memiro.entities.pricing.quotation import PricingVerdict
from tests.common.factory.catalog import (
    BACKLIGHT,
    CONTOUR,
    HEATING,
    MOUNT,
    NO_HEATING,
    WITH_HEATING,
    demo_choices,
    demo_product,
    demo_product_with_value,
    demo_settings,
)


@st.composite
def dimensions(draw: st.DrawFn) -> Dimensions:
    """Draw a pair of sides inside the input bounds the form allows."""
    sides = st.integers(min_value=MIN_SIDE_MM, max_value=MAX_SIDE_MM)
    return Dimensions(
        width=Millimeters(value=draw(sides)),
        height=Millimeters(value=draw(sides)),
    )


@st.composite
def configurations(draw: st.DrawFn) -> dict[AttributeId, AttributeValueId]:
    """Draw what a customer may replace on the canonical mirror: its own attributes, values of theirs."""
    choices = demo_choices()
    attributes = draw(st.lists(st.sampled_from(list(choices)), unique=True, max_size=len(choices)))
    return {attribute_id: draw(st.sampled_from(choices[attribute_id])) for attribute_id in attributes}


@st.composite
def _rotated_limit_case(
    draw: st.DrawFn,
    *,
    fits: bool,
) -> tuple[Dimensions, Dimensions, Millimeters, Millimeters, PricingVerdict]:
    """Draw two rotations and coherent bounds for one expected limit verdict."""
    long_side = draw(st.integers(min_value=MIN_SIDE_MM + 2, max_value=MAX_SIDE_MM))
    short_side = draw(st.integers(min_value=MIN_SIDE_MM + 1, max_value=long_side - 1))
    first = Dimensions(width=Millimeters(value=long_side), height=Millimeters(value=short_side))
    rotated = Dimensions(width=Millimeters(value=short_side), height=Millimeters(value=long_side))
    if fits:
        long_limit = draw(st.sampled_from([0, long_side, MAX_SIDE_MM]))
        short_limit = draw(st.sampled_from([0, short_side, MAX_SIDE_MM]))
        verdict = PricingVerdict.PRICED
    elif draw(st.booleans()):
        long_limit = draw(st.integers(min_value=1, max_value=long_side - 1))
        short_limit = draw(st.sampled_from([0, short_side, MAX_SIDE_MM]))
        verdict = PricingVerdict.BEYOND_LIMITS
    else:
        long_limit = draw(st.sampled_from([0, long_side, MAX_SIDE_MM]))
        short_limit = draw(st.integers(min_value=1, max_value=short_side - 1))
        verdict = PricingVerdict.BEYOND_LIMITS
    return (
        first,
        rotated,
        Millimeters(value=long_limit),
        Millimeters(value=short_limit),
        verdict,
    )


@st.composite
def rotated_limit_cases(
    draw: st.DrawFn,
) -> tuple[Dimensions, Millimeters, Millimeters, PricingVerdict]:
    """Draw one rotated or unrotated size with coherent production bounds."""
    first, rotated, long_limit, short_limit, verdict = draw(_rotated_limit_case(fits=draw(st.booleans())))
    size = draw(st.sampled_from([first, rotated]))
    return size, long_limit, short_limit, verdict


@st.composite
def pricing_cases(
    draw: st.DrawFn,
) -> tuple[Dimensions, dict[AttributeId, AttributeValueId]]:
    """Draw one coherent size and customer configuration."""
    return draw(dimensions()), draw(configurations())


@st.composite
def customer_gate_cases(
    draw: st.DrawFn,
) -> tuple[Product, PricingSettings, Dimensions, PricingVerdict, bool]:
    """Draw one coherent customer question and its expected quotation shape."""
    verdict = draw(st.sampled_from(list(PricingVerdict)))
    sides = st.integers(min_value=MIN_SIDE_MM + 1, max_value=MAX_SIDE_MM)
    size = Dimensions(
        width=Millimeters(value=draw(sides)),
        height=Millimeters(value=draw(sides)),
    )
    product = demo_product()
    pricing_settings = demo_settings()
    if verdict is PricingVerdict.HIDDEN:
        product = replace(product, hides_calculated_price=True)
    elif verdict is PricingVerdict.NOT_PRICEABLE:
        product = replace(
            product,
            declared_values=[
                declaration for declaration in product.declared_values if declaration.attribute_id != MOUNT
            ],
        )
    elif verdict is PricingVerdict.BEYOND_LIMITS:
        pricing_settings = replace(
            pricing_settings,
            max_long_side_mm=Millimeters(value=size.long_side.value - 1),
        )
    carries_price = verdict in {PricingVerdict.PRICED, PricingVerdict.HIDDEN}
    return product, pricing_settings, size, verdict, carries_price


@st.composite
def complete_products(draw: st.DrawFn) -> Product:
    """Draw a product whose dependent declaration is coherent with its present parent."""
    product = demo_product()
    if draw(st.booleans()):
        product = demo_product_with_value(BACKLIGHT, CONTOUR)
        declarations = list(product.declared_values)
        declarations.append(
            DeclaredValue(
                attribute_id=HEATING,
                configured=ConfiguredValue(
                    value_id=draw(st.sampled_from([WITH_HEATING, NO_HEATING])),
                    quantity=None,
                ),
            )
        )
        return replace(product, declared_values=declarations)
    return product


@st.composite
def incomplete_products(draw: st.DrawFn) -> Product:
    """Draw a product missing one required root or its newly applicable child declaration."""
    product = demo_product()
    missing_attribute = draw(st.sampled_from([*demo_choices(), HEATING]))
    if missing_attribute == HEATING:
        declarations = demo_product_with_value(BACKLIGHT, CONTOUR).declared_values
    else:
        declarations = [
            declaration for declaration in product.declared_values if declaration.attribute_id != missing_attribute
        ]
    return replace(product, declared_values=declarations)


@st.composite
def fractional_quantities(draw: st.DrawFn) -> Decimal:
    """Draw one non-integral decimal quantity."""
    fractions = st.tuples(
        st.integers(min_value=0, max_value=20),
        st.integers(min_value=1, max_value=9),
    ).map(lambda parts: Decimal(parts[0]) + Decimal(parts[1]) / Decimal(10))
    return draw(fractions)
