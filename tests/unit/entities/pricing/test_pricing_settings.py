from dataclasses import replace
from decimal import Decimal

import pytest

from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.errors.pricing import DuplicateSizeSurchargeError, InvalidSurchargeFactorError
from memiro.entities.pricing.pricing_settings import SizeSurcharge
from tests.common.factory.catalog import demo_settings


def _dimensions(width: int, height: int) -> Dimensions:
    return Dimensions(width=Millimeters(value=width), height=Millimeters(value=height))


def _surcharge(from_long_side_mm: int, factor: str) -> SizeSurcharge:
    return SizeSurcharge(
        from_long_side_mm=Millimeters(value=from_long_side_mm),
        factor=Decimal(factor),
    )


@pytest.mark.parametrize("factor", ["1", "0.99"])
def test_a_size_surcharge_factor_must_raise_the_price(factor: str) -> None:
    """A factor at or below one raises INVALID_SURCHARGE_FACTOR."""
    with pytest.raises(InvalidSurchargeFactorError, match=f"Invalid size-surcharge factor: {factor}"):
        _surcharge(2200, factor)


def test_size_surcharge_thresholds_are_unique_inside_pricing_settings() -> None:
    """Two tiers starting at 2200 mm raise DUPLICATE_SIZE_SURCHARGE."""
    tiers = (_surcharge(2200, "1.25"), _surcharge(2200, "1.5"))

    with pytest.raises(DuplicateSizeSurchargeError, match="Duplicate size-surcharge threshold: 2200 mm"):
        demo_settings(size_surcharges=tiers)


@pytest.mark.parametrize(
    "dimensions",
    [
        _dimensions(2300, 600),
        _dimensions(600, 2300),
    ],
)
def test_the_highest_reached_size_surcharge_follows_the_rotated_long_side(dimensions: Dimensions) -> None:
    """A rotated 2300 mm side reaches the 2200 tier rather than the 1800 tier."""
    expected = _surcharge(2200, "1.25")
    pricing_settings = demo_settings(
        size_surcharges=(
            _surcharge(2500, "1.5"),
            expected,
            _surcharge(1800, "1.1"),
        ),
    )

    actual = pricing_settings.size_surcharge_for(dimensions)

    assert actual == expected


def test_empty_size_surcharges_leave_every_size_without_a_tier() -> None:
    """An empty tier collection means the size surcharge is disabled."""
    pricing_settings = demo_settings()

    surcharge = pricing_settings.size_surcharge_for(_dimensions(3000, 600))

    assert surcharge is None


@pytest.mark.parametrize(
    "dimensions",
    [
        _dimensions(400, 1900),
        _dimensions(1900, 400),
    ],
)
def test_production_limits_follow_the_rotated_long_and_short_sides(dimensions: Dimensions) -> None:
    """A 400 x 1900 product fits the same rotated production bounds as 1900 x 400."""
    settings = replace(
        demo_settings(),
        max_long_side_mm=Millimeters(value=2000),
        max_short_side_mm=Millimeters(value=500),
    )

    assert settings.is_within_limits(dimensions)


def test_zero_production_limits_leave_every_dimension_within_bounds() -> None:
    """Zero production bounds leave both sides unlimited."""
    settings = replace(
        demo_settings(),
        max_long_side_mm=Millimeters(value=0),
        max_short_side_mm=Millimeters(value=0),
    )

    assert settings.is_within_limits(_dimensions(10_000, 9000))


@pytest.mark.parametrize(
    "dimensions",
    [
        _dimensions(2100, 400),
        _dimensions(1900, 600),
    ],
)
def test_a_product_beyond_either_production_limit_is_outside_the_limits(dimensions: Dimensions) -> None:
    """A side over its production bound is outside the limits."""
    settings = replace(
        demo_settings(),
        max_long_side_mm=Millimeters(value=2000),
        max_short_side_mm=Millimeters(value=500),
    )

    assert not settings.is_within_limits(dimensions)
