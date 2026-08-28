from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

import pytest

from memiro.entities.catalog.product.entity import ConfiguredValue, DeclaredValue, Product
from tests.common.factory.catalog import ALUMINIUM, CATEGORY, FRAME, HEATING, demo_product


def test_a_product_tells_what_it_declared_on_an_attribute() -> None:
    """A product answers with the declaration the owner made on the attribute."""
    product = demo_product()

    declared = product.declared(FRAME)

    assert declared == DeclaredValue(
        attribute_id=FRAME,
        configured=ConfiguredValue(value_id=ALUMINIUM, quantity=None),
    )


def test_a_product_declares_nothing_on_an_attribute_it_never_had() -> None:
    """Heating is in the dictionary but not on this mirror, and the product says so."""
    product = demo_product()

    assert product.declared(HEATING) is None


def test_a_numeric_declaration_keeps_its_fractional_quantity() -> None:
    """A numeric declaration keeps an exact fractional Decimal and names no dictionary row."""
    declaration = DeclaredValue(
        attribute_id=HEATING,
        configured=ConfiguredValue(value_id=None, quantity=Decimal("2.5")),
    )

    assert declaration == DeclaredValue(
        attribute_id=HEATING,
        configured=ConfiguredValue(value_id=None, quantity=Decimal("2.5")),
    )


def test_a_configured_value_rejects_two_representations() -> None:
    """A configured value cannot name a dictionary row and a quantity together."""
    with pytest.raises(RuntimeError, match="Configured value cannot name both"):
        ConfiguredValue(value_id=ALUMINIUM, quantity=Decimal("2.5"))


def test_an_unfinished_product_declaration_keeps_both_representations_empty() -> None:
    """An unfinished declaration remains representable so the product can answer NOT_PRICEABLE."""
    declaration = DeclaredValue(
        attribute_id=FRAME,
        configured=ConfiguredValue(value_id=None, quantity=None),
    )

    assert declaration == DeclaredValue(
        attribute_id=FRAME,
        configured=ConfiguredValue(value_id=None, quantity=None),
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
