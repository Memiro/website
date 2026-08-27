from decimal import Decimal

import pytest

from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.common.money import Money
from memiro.entities.errors.attribute import InvalidFactorRateError


def test_a_tariff_charges_a_fractional_consumption() -> None:
    """2.8 linear metres of an aluminium frame at 2 200 RUB come out at 6 160 RUB."""
    rate = Rate(amount=Money(amount=Decimal(2200)), unit=Unit.LINEAR_METER)

    assert rate.charge(Decimal("2.8")) == Money(amount=Decimal(6160))


def test_a_zero_tariff_is_free_and_says_so() -> None:
    """A free value describes the product without costing anything."""
    rate = Rate(amount=Money(amount=Decimal(0)), unit=Unit.PIECE)

    assert rate.is_free()


def test_a_factor_cannot_be_charged_per_unit() -> None:
    """Charging a FACTOR is mixed-up units in the calculation code — a defect, not a refusal."""
    rate = Rate(amount=Money(amount=Decimal("1.5")), unit=Unit.FACTOR)

    with pytest.raises(RuntimeError):
        rate.charge(Decimal(1))


def test_a_factor_rate_rejects_zero() -> None:
    """A zero factor would annihilate the blade and the frame, and is refused with INVALID_FACTOR_RATE."""
    with pytest.raises(InvalidFactorRateError):
        Rate(amount=Money(amount=Decimal(0)), unit=Unit.FACTOR)


def test_money_per_unit_is_not_a_multiplier() -> None:
    """Reading a per-unit tariff as a factor is the same defect seen from the other side."""
    rate = Rate(amount=Money(amount=Decimal(4500)), unit=Unit.SQUARE_METER)

    with pytest.raises(RuntimeError):
        rate.as_factor()
