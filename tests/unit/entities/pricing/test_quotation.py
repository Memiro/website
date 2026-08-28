from decimal import Decimal

import pytest

from memiro.entities.common.money import Money
from memiro.entities.pricing.quotation import PricingVerdict, Quotation


def test_a_priced_quotation_carries_its_total() -> None:
    """PRICED means the price is calculated and named."""
    quotation = Quotation(verdict=PricingVerdict.PRICED, total=Money(amount=Decimal(8900)), breakdown=())

    assert quotation == Quotation(
        verdict=PricingVerdict.PRICED,
        total=Money(amount=Decimal(8900)),
        breakdown=(),
    )


def test_a_hidden_quotation_keeps_its_total_for_internal_consumers() -> None:
    """HIDDEN means the price exists even though the storefront cannot name it."""
    quotation = Quotation(verdict=PricingVerdict.HIDDEN, total=Money(amount=Decimal(8900)), breakdown=())

    assert quotation == Quotation(verdict=PricingVerdict.HIDDEN, total=Money(amount=Decimal(8900)), breakdown=())


def test_a_beyond_limits_quotation_carries_no_total() -> None:
    """BEYOND_LIMITS leaves the calculation without a named price."""
    quotation = Quotation(verdict=PricingVerdict.BEYOND_LIMITS, total=None, breakdown=())

    assert quotation == Quotation(verdict=PricingVerdict.BEYOND_LIMITS, total=None, breakdown=())


def test_a_not_priceable_quotation_carries_no_total() -> None:
    """NOT_PRICEABLE leaves the calculation without a named price."""
    quotation = Quotation(verdict=PricingVerdict.NOT_PRICEABLE, total=None, breakdown=())

    assert quotation == Quotation(verdict=PricingVerdict.NOT_PRICEABLE, total=None, breakdown=())


def test_a_priced_quotation_without_a_total_is_a_defect() -> None:
    """A verdict disagreeing with the presence of a total cannot happen and leaves as a 500."""
    with pytest.raises(RuntimeError):
        Quotation(verdict=PricingVerdict.PRICED, total=None, breakdown=())
