from decimal import Decimal

import pytest

from memiro.entities.common.measure import Area, Dimensions, Millimeters
from memiro.entities.errors.measure import EmptyDimensionsError, NegativeMeasureError


def test_a_millimeter_rejects_a_negative_value() -> None:
    """A negative size does not exist and is refused with NEGATIVE_MEASURE."""
    with pytest.raises(NegativeMeasureError):
        Millimeters(value=-1)


def test_a_millimeter_accepts_zero() -> None:
    """Zero is legal: it means "no limit" where a limit is expected, and nothing on its own."""
    assert Millimeters(value=0).value == 0


def test_dimensions_reject_a_side_of_zero() -> None:
    """A product with no side does not exist and is refused with EMPTY_DIMENSIONS."""
    with pytest.raises(EmptyDimensionsError):
        Dimensions(width=Millimeters(value=0), height=Millimeters(value=600))


def test_dimensions_keep_the_sides_the_way_they_were_entered() -> None:
    """The storefront shows the customer his own pair, not a reordered one."""
    dimensions = Dimensions(width=Millimeters(value=400), height=Millimeters(value=1900))

    assert (dimensions.width.value, dimensions.height.value) == (400, 1900)


def test_a_turned_product_has_the_same_long_and_short_side() -> None:
    """1900 x 400 and 400 x 1900 are one size: the product is turned."""
    upright = Dimensions(width=Millimeters(value=400), height=Millimeters(value=1900))
    lying = Dimensions(width=Millimeters(value=1900), height=Millimeters(value=400))

    assert (upright.long_side, upright.short_side) == (lying.long_side, lying.short_side)


def test_an_area_comes_out_in_full_square_meters() -> None:
    """800 x 600 mm is 0.48 m2 — the area is fractional and is never rounded up to a square metre."""
    dimensions = Dimensions(width=Millimeters(value=800), height=Millimeters(value=600))

    assert dimensions.area() == Area(value=Decimal("0.48"))


def test_a_perimeter_is_twice_the_sum_of_the_sides() -> None:
    """800 x 600 mm gives 2.8 linear metres of rim."""
    dimensions = Dimensions(width=Millimeters(value=800), height=Millimeters(value=600))

    assert dimensions.perimeter().value == Decimal("2.8")


def test_a_small_area_is_raised_to_the_minimum_one() -> None:
    """Cutting a sheet gets no cheaper on a small mirror, so the area is lifted to the minimum."""
    area = Area(value=Decimal("0.12"))

    assert area.at_least(Area(value=Decimal("0.25"))) == Area(value=Decimal("0.25"))


def test_a_large_area_is_left_alone_by_the_minimum() -> None:
    """The minimum area is a floor, not a replacement."""
    area = Area(value=Decimal("0.48"))

    assert area.at_least(Area(value=Decimal("0.25"))) == area
