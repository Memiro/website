from memiro.entities.catalog.product.entity import DeclaredValue
from tests.common.factory.catalog import ALUMINIUM, FRAME, HEATING, demo_product


def test_a_product_tells_what_it_declared_on_an_attribute() -> None:
    """A product answers with the declaration the owner made on the attribute."""
    product = demo_product()

    declared = product.declared(FRAME)

    assert declared == DeclaredValue(attribute_id=FRAME, value_id=ALUMINIUM)


def test_a_product_declares_nothing_on_an_attribute_it_never_had() -> None:
    """Heating is in the dictionary but not on this mirror, and the product says so."""
    product = demo_product()

    assert product.declared(HEATING) is None
