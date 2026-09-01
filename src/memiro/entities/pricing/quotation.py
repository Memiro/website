from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from memiro.entities.catalog.attribute.rate import Rate
from memiro.entities.common.identifiers import AttributeId, AttributeValueId
from memiro.entities.common.measure import Millimeters
from memiro.entities.common.money import Money


class PricingVerdict(StrEnum):
    """What happened to the calculation.

    Explicit values: the verdict code leaves for the storefront, which makes
    it part of the external contract (§4). The refusing verdicts arrive with
    the gates of the customer's question.
    """

    PRICED = "PRICED"
    HIDDEN = "HIDDEN"
    BEYOND_LIMITS = "BEYOND_LIMITS"
    NOT_PRICEABLE = "NOT_PRICEABLE"


# The verdicts that carry a total. Kept as a set so the invariant stays in one
# place when a new total-bearing verdict is added.
_VERDICTS_WITH_TOTAL = frozenset({PricingVerdict.PRICED, PricingVerdict.HIDDEN})


def carries_total(verdict: PricingVerdict) -> bool:
    """Tell whether a verdict is one that priced the mirror."""
    return verdict in _VERDICTS_WITH_TOTAL


@dataclass(frozen=True, slots=True)
class QuotationLine:
    """One line of the calculation: a dictionary value, its consumption, its tariff and the sum."""

    attribute_id: AttributeId
    value_id: AttributeValueId
    quantity: Decimal
    rate: Rate
    amount: Money


@dataclass(frozen=True, slots=True)
class Quotation:
    """The result of the calculation — the only thing ``price_product`` returns.

    One object instead of a scattering of booleans: the verdict says what
    happened, and invalid combinations of state are unrepresentable.
    """

    verdict: PricingVerdict
    total: Money | None
    breakdown: tuple[QuotationLine, ...]
    size_surcharge_from_long_side_mm: Millimeters | None = None

    def __post_init__(self) -> None:
        """Hold the verdict/total invariant: a mismatch is a defect, not a refusal (§12.3)."""
        if (self.total is not None) is not carries_total(self.verdict):
            msg = f"Verdict {self.verdict} disagrees with the presence of a total"
            raise RuntimeError(msg)
        if self.total is None and self.breakdown:
            msg = f"Verdict {self.verdict} carries no total and must carry no breakdown"
            raise RuntimeError(msg)
        if self.total is None and self.size_surcharge_from_long_side_mm is not None:
            msg = f"Verdict {self.verdict} did no pricing and cannot carry a size-surcharge threshold"
            raise RuntimeError(msg)
