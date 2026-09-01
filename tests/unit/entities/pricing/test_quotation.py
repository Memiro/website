from decimal import Decimal

import pytest

from memiro.entities.common.measure import Millimeters
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


def test_a_hidden_quotation_keeps_the_applied_size_surcharge_threshold() -> None:
    """HIDDEN conceals money from the storefront but retains the applied public threshold."""
    quotation = Quotation(
        verdict=PricingVerdict.HIDDEN,
        total=Money(amount=Decimal(8900)),
        breakdown=(),
        size_surcharge_from_long_side_mm=Millimeters(value=2200),
    )

    assert quotation == Quotation(
        verdict=PricingVerdict.HIDDEN,
        total=Money(amount=Decimal(8900)),
        breakdown=(),
        size_surcharge_from_long_side_mm=Millimeters(value=2200),
    )


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


def test_a_refusing_quotation_cannot_claim_an_applied_size_surcharge() -> None:
    """A refusal that did no arithmetic cannot carry a size-surcharge threshold."""
    with pytest.raises(RuntimeError, match="cannot carry a size-surcharge threshold"):
        Quotation(
            verdict=PricingVerdict.NOT_PRICEABLE,
            total=None,
            breakdown=(),
            size_surcharge_from_long_side_mm=Millimeters(value=2200),
        )


def test_a_priced_quotation_hands_over_the_total_it_carries() -> None:
    """A verdict that priced the mirror gives its consumer the number."""
    quotation = Quotation(verdict=PricingVerdict.PRICED, total=Money(amount=Decimal(8900)), breakdown=())

    assert quotation.settled_total() == Money(amount=Decimal(8900))


def test_a_refusal_asked_for_a_total_is_a_defect() -> None:
    """A refusal has no number to give, and asking it for one is a defect that leaves as a 500."""
    quotation = Quotation(verdict=PricingVerdict.BEYOND_LIMITS, total=None, breakdown=())

    with pytest.raises(RuntimeError, match="left the calculation with no total"):
        quotation.settled_total()


def test_a_priced_quotation_shows_its_total_to_the_storefront() -> None:
    """PRICED is the one verdict whose total the storefront may show."""
    quotation = Quotation(verdict=PricingVerdict.PRICED, total=Money(amount=Decimal(8900)), breakdown=())

    assert quotation.customer_total() == Money(amount=Decimal(8900))


def test_a_hidden_quotation_shows_no_total_to_the_storefront() -> None:
    """HIDDEN keeps its total for the owner and shows none to the storefront (ADR-0008)."""
    quotation = Quotation(verdict=PricingVerdict.HIDDEN, total=Money(amount=Decimal(8900)), breakdown=())

    assert quotation.customer_total() is None


def test_a_beyond_limits_quotation_shows_no_total_to_the_storefront() -> None:
    """A refusal leaves the storefront without a price to show."""
    quotation = Quotation(verdict=PricingVerdict.BEYOND_LIMITS, total=None, breakdown=())

    assert quotation.customer_total() is None
