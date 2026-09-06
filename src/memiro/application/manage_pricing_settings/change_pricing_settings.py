from decimal import Decimal

import structlog
from pydantic import BaseModel, Field

from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.common.input_limits import (
    MAX_AREA_M2,
    MAX_ORDER_TOTAL,
    MAX_SIDE_MM,
    MAX_SIZE_SURCHARGES,
    MAX_SURCHARGE_FACTOR,
)
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.entities.common.measure import Area, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.pricing.pricing_settings import ChangePricingSettingsData, SizeSurchargeData
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

# Zero is a bound the owner may type: it means the studio takes on any size
# (``pricing-settings.md``, rule 2).
NO_PRODUCTION_LIMIT = 0

logger: Logger = structlog.get_logger(__name__)


class SizeSurchargeRowForm(BaseModel):
    """One surcharge tier as the owner's screen submits it."""

    from_long_side_mm: int = Field(ge=NO_PRODUCTION_LIMIT, le=MAX_SIDE_MM)
    # The bound is an input bound and stops at "a number the arithmetic
    # survives"; that the factor must actually raise the price is the domain's
    # rule, and refusing it here would beat the domain to its own refusal.
    factor: Decimal = Field(ge=0, le=MAX_SURCHARGE_FACTOR)


class ChangePricingSettingsForm(BaseModel):
    """The bounds of calculation as the owner wants them to end up, tiers included."""

    min_area: Decimal = Field(ge=0, le=MAX_AREA_M2)
    min_order_total: Decimal = Field(ge=0, le=MAX_ORDER_TOTAL)
    max_long_side_mm: int = Field(ge=NO_PRODUCTION_LIMIT, le=MAX_SIDE_MM)
    max_short_side_mm: int = Field(ge=NO_PRODUCTION_LIMIT, le=MAX_SIDE_MM)
    surcharges: list[SizeSurchargeRowForm] = Field(
        default_factory=list[SizeSurchargeRowForm],
        max_length=MAX_SIZE_SURCHARGES,
    )


@interactor
class ChangePricingSettings:
    """Interactor for restating the bounds of calculation and the whole surcharge table."""

    uow: UoW
    pricing_settings_gateway: PricingSettingsGateway
    clock: Clock

    async def execute(self, data: ChangePricingSettingsForm) -> None:
        """Replace the calculation parameters of the site and commit their transaction."""
        logger.debug("Changing the pricing settings")
        # No lock on the root: the command overwrites every bound and the whole
        # tier table from the owner's form, so there is nothing read here that
        # a competitor could make stale.
        settings = await self.pricing_settings_gateway.get_with_surcharges()
        if settings is None:
            logger.warning("The site has no pricing settings to change")
            raise PricingSettingsNotFoundError
        settings.restate(
            ChangePricingSettingsData(
                min_area=Area(value=data.min_area),
                min_order_total=Money(amount=data.min_order_total),
                max_long_side_mm=Millimeters(value=data.max_long_side_mm),
                max_short_side_mm=Millimeters(value=data.max_short_side_mm),
                surcharges=tuple(
                    SizeSurchargeData(
                        from_long_side_mm=Millimeters(value=row.from_long_side_mm),
                        factor=row.factor,
                    )
                    for row in data.surcharges
                ),
            ),
            clock=self.clock,
        )
        await self.uow.commit()
        logger.info("Pricing settings changed", surcharge_count=len(data.surcharges))
