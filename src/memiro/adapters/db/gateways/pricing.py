from typing import override

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memiro.adapters.db.tables import pricing_settings_table
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.entities.pricing.pricing_settings import PRICING_SETTINGS_ID, PricingSettings


class SAPricingSettingsGateway(PricingSettingsGateway):
    """SQLAlchemy-based implementation of ``PricingSettingsGateway``."""

    def __init__(self, session: AsyncSession) -> None:
        """Keep the request-scoped session the gateway queries through."""
        self._session = session

    @override
    async def get(self) -> PricingSettings | None:
        """Load the settings row by its known id — the site has exactly one."""
        result = await self._session.execute(
            select(PricingSettings).where(pricing_settings_table.c.id == PRICING_SETTINGS_ID),
        )
        return result.scalar_one_or_none()
