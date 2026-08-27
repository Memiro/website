from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True, order=True)
class Money:
    """A sum in roubles — the only monetary type of the domain."""

    amount: Decimal

    def __post_init__(self) -> None:
        """Reject a negative sum: ``Money`` is an amount, and amounts do not go below zero."""
        # A negative total is never a business answer to the customer — it
        # means the calculation is broken — so it leaves as a 500, not a 4xx.
        if self.amount < 0:
            msg = f"Money cannot be negative: {self.amount}"
            raise RuntimeError(msg)

    def __add__(self, other: "Money") -> "Money":
        """Add two sums; kopecks are kept in full — nothing rounds here."""
        return Money(amount=self.amount + other.amount)

    def __mul__(self, quantity: Decimal) -> "Money":
        """Multiply the sum by a consumption or a factor — never by another ``Money``."""
        return Money(amount=self.amount * quantity)
