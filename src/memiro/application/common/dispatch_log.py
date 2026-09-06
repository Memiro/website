"""What the after-commit subscribers of one request did, for the screen that started it (ADR-0014)."""

from dataclasses import dataclass


@dataclass(slots=True)
class DispatchLog:
    """Tally of the after-commit work one request set off."""

    repriced_products: int = 0
    repricing_ran: bool = False
    failed: bool = False

    def record(self, repriced_products: int) -> None:
        """Add what one repricing subscriber moved, a run that moved nothing included."""
        self.repriced_products += repriced_products
        self.repricing_ran = True

    def record_failure(self) -> None:
        """Remember that a subscriber did not finish."""
        self.failed = True

    def merge(self, other: "DispatchLog") -> None:
        """Add what the subscribers of one more command did."""
        self.repriced_products += other.repriced_products
        self.repricing_ran = self.repricing_ran or other.repricing_ran
        self.failed = self.failed or other.failed
