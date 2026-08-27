from decimal import Decimal

import pytest

from memiro.entities.common.money import Money


def test_money_rejects_a_negative_sum() -> None:
    """A negative sum is a defect of the calculation, not a refusal, so it is a RuntimeError."""
    with pytest.raises(RuntimeError, match="cannot be negative"):
        Money(amount=Decimal(-1))


def test_two_sums_add_up_keeping_their_kopecks() -> None:
    """Intermediate sums stay full: rounding happens once, at the very end of the calculation."""
    total = Money(amount=Decimal("2160.55")) + Money(amount=Decimal("6160.45"))

    assert total == Money(amount=Decimal("8321.00"))


def test_a_sum_multiplied_by_a_consumption_keeps_the_fraction() -> None:
    """Two and a half linear metres are two and a half, not three."""
    total = Money(amount=Decimal(2200)) * Decimal("2.5")

    assert total == Money(amount=Decimal(5500))


def test_sums_compare_by_amount() -> None:
    """Comparison carries the minimum order total and the "price from" of a product."""
    assert Money(amount=Decimal(1125)) < Money(amount=Decimal(2000))
