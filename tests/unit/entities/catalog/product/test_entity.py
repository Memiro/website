from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

import pytest

from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.catalog.product.entity import DeclaredValue, Product
from tests.common.factory.catalog import ALUMINIUM, CATEGORY, FRAME, HEATING, demo_product


def test_a_product_tells_what_it_declared_on_an_attribute() -> None:
    """A product answers with the declaration the owner made on the attribute."""
    product = demo_product()

    declared = product.declared(FRAME)

    assert declared == DeclaredValue(
        attribute_id=FRAME,
        chosen=ChosenValue(value_id=ALUMINIUM, quantity=None),
    )


def test_a_product_declares_nothing_on_an_attribute_it_never_had() -> None:
    """Heating is in the dictionary but not on this mirror, and the product says so."""
    product = demo_product()

    assert product.declared(HEATING) is None


def test_a_numeric_declaration_keeps_its_fractional_quantity() -> None:
    """A numeric declaration keeps an exact fractional Decimal and names no dictionary row."""
    declaration = DeclaredValue(
        attribute_id=HEATING,
        chosen=ChosenValue(value_id=None, quantity=Decimal("2.5")),
    )

    assert declaration == DeclaredValue(
        attribute_id=HEATING,
        chosen=ChosenValue(value_id=None, quantity=Decimal("2.5")),
    )


def test_an_unfinished_product_declaration_keeps_both_representations_empty() -> None:
    """An unfinished declaration remains representable so the product can answer NOT_PRICEABLE."""
    declaration = DeclaredValue(
        attribute_id=FRAME,
        chosen=ChosenValue(value_id=None, quantity=None),
    )

    assert declaration == DeclaredValue(
        attribute_id=FRAME,
        chosen=ChosenValue(value_id=None, quantity=None),
    )


def test_a_product_requires_its_category() -> None:
    """A product cannot exist without an explicit category identity."""
    constructor = cast("Any", Product)

    with pytest.raises(TypeError):
        constructor(id=uuid4(), name="Mirror", slug="mirror", is_published=False)


def test_a_product_requires_an_explicit_publication_state() -> None:
    """A product cannot become public through a constructor default."""
    constructor = cast("Any", Product)

    with pytest.raises(TypeError):
        constructor(id=uuid4(), category_id=CATEGORY, name="Mirror", slug="mirror")


def test_a_product_copies_the_set_it_was_given_to_declare() -> None:
    """A list edited after the command ran never leaks a new value into the aggregate."""
    product = demo_product()
    declarations = list(product.declared_values)
    product.declare_values(declarations)

    declarations.append(DeclaredValue(attribute_id=HEATING, chosen=ChosenValue(value_id=None, quantity=None)))

    assert product.declared(HEATING) is None


def test_a_product_refuses_a_declaration_set_assigned_from_outside() -> None:
    """The declared set is not an assignable field: the command method is the only way in."""
    product = cast("Any", demo_product())

    with pytest.raises(AttributeError):
        product.declared_values = []


def test_a_product_takes_a_new_declaration_set_through_its_command_method() -> None:
    """Declaring replaces the whole set the owner had declared before."""
    product = demo_product()
    heating = DeclaredValue(attribute_id=HEATING, chosen=ChosenValue(value_id=None, quantity=None))

    product.declare_values([heating])

    assert product.declared_values == (heating,)
