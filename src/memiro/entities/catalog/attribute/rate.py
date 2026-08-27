from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from memiro.entities.common.money import Money
from memiro.entities.errors.attribute import InvalidFactorRateError


class Unit(StrEnum):
    """What the consumption of a dictionary value is measured in.

    Explicit values: the unit is visible in the xlsx workbook and on the
    "Materials and prices" screen, which makes it part of the external
    contract (§4).
    """

    PIECE = "PIECE"
    LINEAR_METER = "LINEAR_METER"
    SQUARE_METER = "SQUARE_METER"
    FACTOR = "FACTOR"


@dataclass(frozen=True, slots=True)
class Rate:
    """The tariff of a dictionary value: what one unit of it costs."""

    amount: Money
    unit: Unit

    def __post_init__(self) -> None:
        """Reject a ``FACTOR`` of zero: it would annihilate the price instead of scaling it.

        Zero is a legal tariff — "free" — for everything charged per unit, but
        a multiplier of zero collapses the blade and the frame and leaves the
        customer the minimum order total. "No surcharge for this shape" is a
        factor of one, and the owner is refused the other spelling where he
        types it.
        """
        if self.unit is Unit.FACTOR and self.is_free():
            raise InvalidFactorRateError

    def is_free(self) -> bool:
        """Tell whether the value describes the product without costing anything."""
        return self.amount.amount == 0

    def charge(self, quantity: Decimal) -> Money:
        """Multiply the tariff by a fractional consumption — the only place this happens."""
        if self.unit is Unit.FACTOR:
            msg = "A FACTOR rate multiplies what is already counted; it is not charged per unit"
            raise RuntimeError(msg)
        return self.amount * quantity

    def as_factor(self) -> Decimal:
        """Return the multiplier of a ``FACTOR`` rate."""
        if self.unit is not Unit.FACTOR:
            msg = f"A {self.unit} rate is money per unit, not a multiplier"
            raise RuntimeError(msg)
        return self.amount.amount
