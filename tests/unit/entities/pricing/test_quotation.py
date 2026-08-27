from decimal import Decimal

import pytest

from memiro.entities.common.money import Money
from memiro.entities.pricing.quotation import PricingVerdict, Quotation


def test_a_priced_quotation_carries_its_total() -> None:
    """PRICED means the price is calculated and named."""
    quotation = Quotation(verdict=PricingVerdict.PRICED, total=Money(amount=Decimal(8900)), breakdown=())

    assert quotation.total == Money(amount=Decimal(8900))


def test_a_priced_quotation_without_a_total_is_a_defect() -> None:
    """A verdict disagreeing with the presence of a total cannot happen and leaves as a 500."""
    with pytest.raises(RuntimeError):
        Quotation(verdict=PricingVerdict.PRICED, total=None, breakdown=())
