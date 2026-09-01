from decimal import Decimal

import pytest

from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.errors.product import InvalidQuantityError
from tests.common.factory.catalog import ALUMINIUM


def test_a_chosen_value_rejects_two_representations() -> None:
    """A chosen value cannot name a dictionary row and a quantity together."""
    with pytest.raises(RuntimeError, match="Chosen value cannot name both"):
        ChosenValue(value_id=ALUMINIUM, quantity=Decimal("2.5"))


def test_a_chosen_value_refuses_a_negative_quantity() -> None:
    """A consumption below zero is refused with INVALID_QUANTITY, not carried into the arithmetic."""
    with pytest.raises(InvalidQuantityError):
        ChosenValue(value_id=None, quantity=Decimal(-5))


def test_a_chosen_value_keeps_a_zero_quantity() -> None:
    """Zero stays a chosen consumption: it is a declaration, not an absence."""
    chosen = ChosenValue(value_id=None, quantity=Decimal(0))

    assert chosen.quantity == Decimal(0)
