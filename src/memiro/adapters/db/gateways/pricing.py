from typing import override

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.entities.pricing.pricing_settings import PricingSettings


class SAPricingSettingsGateway(PricingSettingsGateway):
    """SQLAlchemy-based implementation of ``PricingSettingsGateway``."""

    def __init__(self, session: AsyncSession) -> None:
        """Keep the request-scoped session the gateway queries through."""
        self._session = session

    @override
    async def get(self) -> PricingSettings | None:
        """Load the single settings row; the site has one, and it is fetched without an id."""
        result = await self._session.execute(select(PricingSettings))
        return result.scalars().first()
