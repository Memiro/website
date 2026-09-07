from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.catalog.product.entity import DeclaredValue
from memiro.entities.pricing.pricing_service import pricing_gaps
from tests.common.factory.catalog import (
    MOUNT,
    RECTANGULAR,
    SHAPE,
    demo_attributes,
    demo_product,
    demo_product_without,
    demo_shape,
    product_declaring,
)


def test_a_product_missing_a_declaration_names_the_attribute_it_lacks() -> None:
    """The gap of an undeclared root attribute is the attribute itself, by identifier."""
    product = demo_product_without(MOUNT)

    result = pricing_gaps(product, demo_attributes())

    assert result.undeclared == (MOUNT,)


def test_a_product_made_only_of_unpaid_values_says_that_nothing_is_paid() -> None:
    """A complete configuration of factors alone has nothing to charge for."""
    product = product_declaring(
        demo_product(),
        [DeclaredValue(attribute_id=SHAPE, chosen=ChosenValue(value_id=RECTANGULAR, quantity=None))],
    )

    result = pricing_gaps(product, [demo_shape()])

    assert result.nothing_is_paid


def test_a_product_that_declared_nothing_is_not_told_that_nothing_is_paid() -> None:
    """An empty product lacks declarations, and an undeclared attribute may be the paid one."""
    product = product_declaring(demo_product(), [])

    result = pricing_gaps(product, [demo_shape()])

    assert not result.nothing_is_paid


def test_a_complete_and_paid_product_lacks_nothing() -> None:
    """The canonical mirror is priceable, so its gaps are empty on both counts."""
    result = pricing_gaps(demo_product(), demo_attributes())

    assert result.nothing_is_missing()
