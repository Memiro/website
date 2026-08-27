"""Hypothesis strategies of the unit level — the one home for every ``@st.composite``.

The draws are coherent by construction: a configuration is assembled out of
the demo dictionary the way the owner assembles one, so no test has to patch a
drawn value into legality afterwards (§14.7.2).
"""

from hypothesis import strategies as st

from memiro.application.common.input_limits import MAX_SIDE_MM, MIN_SIDE_MM
from memiro.entities.common.identifiers import AttributeId, AttributeValueId
from memiro.entities.common.measure import Dimensions, Millimeters
from tests.common.factory.catalog import demo_attributes, demo_product


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
    values = {attribute.id: [value.id for value in attribute.values] for attribute in demo_attributes()}
    declared = [declaration.attribute_id for declaration in demo_product().declared_values]
    chosen = draw(st.lists(st.sampled_from(declared), unique=True, max_size=len(declared)))
    return {attribute_id: draw(st.sampled_from(values[attribute_id])) for attribute_id in chosen}
