"""What the screen of calculation parameters sends: the whole screen as one command (ADR-0010)."""

from collections.abc import Mapping, Sequence
from typing import Any

from dishka import AsyncContainer

from memiro.application.manage_pricing_settings import (
    ChangePricingSettings,
    ChangePricingSettingsForm,
    SizeSurchargeRowForm,
)
from memiro.presentation.django_admin.writes import sent


def restate_pricing_settings(bounds: Mapping[str, Any], tiers: Sequence[Mapping[str, Any]]) -> None:
    """Send the bounds of calculation and the surcharge table as the one command of the aggregate."""
    form = ChangePricingSettingsForm(
        min_area=bounds["min_area"],
        min_order_total=bounds["min_order_total"],
        max_long_side_mm=bounds["max_long_side_mm"],
        max_short_side_mm=bounds["max_short_side_mm"],
        surcharges=[
            SizeSurchargeRowForm(from_long_side_mm=tier["from_long_side_mm"], factor=tier["factor"]) for tier in tiers
        ],
    )
    sent(lambda scope: _change(scope, form))


async def _change(scope: AsyncContainer, form: ChangePricingSettingsForm) -> None:
    interactor = await scope.get(ChangePricingSettings)
    await interactor.execute(form)
