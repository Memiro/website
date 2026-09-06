"""The owner moves the bounds the price is calculated within, tiers and all.

The screen that sends this command is the Django admin (ticket 04); what is
pinned here is the seam of the interactor itself — the bounds of its input and
the refusal it owes a site whose parameters were never installed.
"""

from decimal import Decimal

import pytest
from dishka import AsyncContainer
from pydantic import ValidationError

from memiro.application.common.input_limits import (
    MAX_AREA_M2,
    MAX_SIDE_MM,
    MAX_SIZE_SURCHARGES,
    MAX_SURCHARGE_FACTOR,
)
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.entities.common.measure import Area
from tests.integration.manage_pricing_settings.arrange import (
    MIN_AREA,
    change_settings,
    load_settings,
    settings_form,
)
from tests.integration.prime import prime_no_pricing_settings

pytestmark = pytest.mark.usefixtures("catalog")


async def test_the_owner_moves_the_bounds_the_calculation_lives_in(container: AsyncContainer) -> None:
    """The parameters the owner submitted are the parameters the next reader gets."""
    await change_settings(container, settings_form(surcharges=((2200, "1.25"),)))

    stored = await load_settings(container)
    assert stored is not None
    assert stored.min_area == Area(value=MIN_AREA)
    assert [tier.factor for tier in stored.size_surcharges] == [Decimal("1.25")]


@pytest.mark.parametrize(
    "form",
    [
        pytest.param({"min_area": MAX_AREA_M2 + 1}, id=None),
        pytest.param({"max_long_side_mm": MAX_SIDE_MM + 1}, id=None),
    ],
)
async def test_a_bound_one_step_over_its_limit_never_reaches_the_domain(
    container: AsyncContainer,
    form: dict[str, object],
) -> None:
    """VALIDATION_ERROR: the input bounds of the form are hit at exactly limit + 1."""
    with pytest.raises(ValidationError):
        await change_settings(container, settings_form(**form))  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


async def test_one_tier_more_than_the_table_holds_never_reaches_the_domain(container: AsyncContainer) -> None:
    """VALIDATION_ERROR: the surcharge table is hit at exactly MAX_SIZE_SURCHARGES + 1."""
    tiers = tuple((100 * number + 100, "1.25") for number in range(MAX_SIZE_SURCHARGES + 1))

    with pytest.raises(ValidationError):
        await change_settings(container, settings_form(surcharges=tiers))


async def test_a_factor_one_step_over_its_limit_never_reaches_the_domain(container: AsyncContainer) -> None:
    """VALIDATION_ERROR: the factor is an input bound too, hit at exactly limit + 1."""
    with pytest.raises(ValidationError):
        await change_settings(container, settings_form(surcharges=((2200, str(MAX_SURCHARGE_FACTOR + 1)),)))


async def test_a_site_whose_parameters_were_never_installed_is_told_so(
    container: AsyncContainer,
    engine: object,
) -> None:
    """PRICING_SETTINGS_NOT_FOUND: without the row the command has nothing to move."""
    await prime_no_pricing_settings(engine)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]

    with pytest.raises(PricingSettingsNotFoundError):
        await change_settings(container, settings_form())
