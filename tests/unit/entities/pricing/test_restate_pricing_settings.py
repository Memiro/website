from decimal import Decimal

import pytest

from memiro.entities.common.measure import Area, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.errors.pricing import DuplicateSizeSurchargeError, InvalidSurchargeFactorError
from memiro.entities.pricing.pricing_settings import (
    ChangePricingSettingsData,
    SizeSurcharge,
    SizeSurchargeData,
)
from tests.clock import LATER, LATER_CLOCK
from tests.common.factory.catalog import demo_settings

# The bounds the owner types into the card, all four different from the demo ones.
MIN_AREA = Area(value=Decimal("0.35"))
MIN_ORDER_TOTAL = Money(amount=Decimal(3000))
MAX_LONG_SIDE = Millimeters(value=3200)
MAX_SHORT_SIDE = Millimeters(value=2500)


def _surcharge(from_long_side_mm: int, factor: str) -> SizeSurcharge:
    return SizeSurcharge(from_long_side_mm=Millimeters(value=from_long_side_mm), factor=Decimal(factor))


def _tier(from_long_side_mm: int, factor: str) -> SizeSurchargeData:
    return SizeSurchargeData(from_long_side_mm=Millimeters(value=from_long_side_mm), factor=Decimal(factor))


def _data(*, surcharges: tuple[SizeSurchargeData, ...] = ()) -> ChangePricingSettingsData:
    """Build the owner's form for the whole screen of calculation parameters."""
    return ChangePricingSettingsData(
        min_area=MIN_AREA,
        min_order_total=MIN_ORDER_TOTAL,
        max_long_side_mm=MAX_LONG_SIDE,
        max_short_side_mm=MAX_SHORT_SIDE,
        surcharges=surcharges,
    )


def test_the_owner_restates_the_bounds_of_calculation() -> None:
    """Every bound the owner typed replaces the one the settings had."""
    settings = demo_settings()

    settings.restate(_data(), clock=LATER_CLOCK)

    assert settings.min_area == MIN_AREA
    assert settings.min_order_total == MIN_ORDER_TOTAL
    assert settings.max_long_side_mm == MAX_LONG_SIDE
    assert settings.max_short_side_mm == MAX_SHORT_SIDE
    assert settings.updated_at == LATER


def test_the_owner_replaces_the_whole_set_of_surcharge_tiers() -> None:
    """The set is replaced, not merged: what the owner did not submit is gone."""
    settings = demo_settings(size_surcharges=[_surcharge(1800, "1.1")])

    settings.restate(_data(surcharges=(_tier(2200, "1.25"),)), clock=LATER_CLOCK)

    assert [(tier.from_long_side_mm, tier.factor) for tier in settings.size_surcharges] == [
        (Millimeters(value=2200), Decimal("1.25")),
    ]


def test_an_empty_set_of_tiers_switches_the_size_surcharge_off() -> None:
    """An empty tier set is the one way to disable the surcharge (ADR-0010)."""
    settings = demo_settings(size_surcharges=[_surcharge(1800, "1.1")])

    settings.restate(_data(), clock=LATER_CLOCK)

    assert settings.size_surcharges == ()


def test_a_restated_set_naming_one_threshold_twice_is_refused() -> None:
    """Two tiers starting at 2200 mm raise DUPLICATE_SIZE_SURCHARGE."""
    settings = demo_settings()

    with pytest.raises(DuplicateSizeSurchargeError, match="Duplicate size-surcharge threshold: 2200 mm"):
        settings.restate(_data(surcharges=(_tier(2200, "1.25"), _tier(2200, "1.5"))), clock=LATER_CLOCK)


def test_a_refused_set_of_tiers_leaves_the_bounds_where_they_were() -> None:
    """The refusal is owed before a single bound is moved: the aggregate is untouched."""
    settings = demo_settings()

    with pytest.raises(DuplicateSizeSurchargeError):
        settings.restate(_data(surcharges=(_tier(2200, "1.25"), _tier(2200, "1.5"))), clock=LATER_CLOCK)

    assert settings.min_area == Area(value=Decimal("0.25"))


def test_a_restated_tier_that_would_not_raise_the_price_is_refused() -> None:
    """A factor at one raises INVALID_SURCHARGE_FACTOR."""
    settings = demo_settings()

    with pytest.raises(InvalidSurchargeFactorError, match="Invalid size-surcharge factor: 1"):
        settings.restate(_data(surcharges=(_tier(2200, "1"),)), clock=LATER_CLOCK)
