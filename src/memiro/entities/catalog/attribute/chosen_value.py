from dataclasses import dataclass
from decimal import Decimal

from memiro.entities.common.identifiers import AttributeValueId
from memiro.entities.errors.product import InvalidQuantityError


@dataclass(frozen=True, slots=True)
class ChosenValue:
    """One chosen attribute value, expressed as either a dictionary row or a quantity."""

    value_id: AttributeValueId | None
    quantity: Decimal | None

    def __post_init__(self) -> None:
        """Reject two simultaneous representations, and a consumption below zero."""
        if self.value_id is not None and self.quantity is not None:
            msg = "Chosen value cannot name both a dictionary row and a quantity"
            raise RuntimeError(msg)
        # Zero is a declaration ("no cutouts"), below zero is not: it would
        # reach ``Rate.charge`` and leave as a 500 from ``Money`` — a refusal
        # the customer is owed as a 4xx instead.
        if self.quantity is not None and self.quantity < 0:
            raise InvalidQuantityError
