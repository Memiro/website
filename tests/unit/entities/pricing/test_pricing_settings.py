from dataclasses import replace

import pytest

from memiro.entities.common.measure import Dimensions, Millimeters
from tests.common.factory.catalog import demo_settings


def _dimensions(width: int, height: int) -> Dimensions:
    return Dimensions(width=Millimeters(value=width), height=Millimeters(value=height))


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
