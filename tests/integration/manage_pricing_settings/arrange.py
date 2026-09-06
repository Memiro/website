"""Forms and readings the calculation-parameter scenarios share."""

from decimal import Decimal

from dishka import AsyncContainer

from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.manage_pricing_settings import (
    ChangePricingSettings,
    ChangePricingSettingsForm,
    SizeSurchargeRowForm,
)
from memiro.entities.pricing.pricing_settings import PricingSettings

# The bounds a test types over the demo ones, so a stored value tells which
# command won.
MIN_AREA = Decimal("0.35")
MIN_ORDER_TOTAL = Decimal(3000)


def settings_form(
    *,
    min_area: Decimal = MIN_AREA,
    max_long_side_mm: int = 3200,
    surcharges: tuple[tuple[int, str], ...] = (),
) -> ChangePricingSettingsForm:
    """Build the owner's whole screen of calculation parameters."""
    return ChangePricingSettingsForm(
        min_area=min_area,
        min_order_total=MIN_ORDER_TOTAL,
        max_long_side_mm=max_long_side_mm,
        max_short_side_mm=2500,
        surcharges=[
            SizeSurchargeRowForm(from_long_side_mm=threshold, factor=Decimal(factor))
            for threshold, factor in surcharges
        ],
    )


async def change_settings(container: AsyncContainer, form: ChangePricingSettingsForm) -> None:
    """Execute one parameter change in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(ChangePricingSettings)
        await interactor.execute(form)


async def load_settings(container: AsyncContainer) -> PricingSettings | None:
    """Read the calculation parameters back in a fresh transaction after a command."""
    async with container() as request:
        gateway: PricingSettingsGateway = await request.get(PricingSettingsGateway)
        return await gateway.get_with_surcharges()
