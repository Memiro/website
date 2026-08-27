from typing import override

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memiro.adapters.db.tables import pricing_settings_table
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.entities.pricing.pricing_settings import PricingSettings


class SAPricingSettingsGateway(PricingSettingsGateway):
    """SQLAlchemy-based implementation of ``PricingSettingsGateway``."""

    def __init__(self, session: AsyncSession) -> None:
        """Keep the request-scoped session the gateway queries through."""
        self._session = session

    @override
    async def get(self) -> PricingSettings | None:
        """Load the single settings row; the site has one, and it is fetched without an id.

        Ordered by id all the same: should a second row ever appear, every
        request must answer with the same one rather than with whatever the
        database returns first.
        """
        result = await self._session.execute(
            select(PricingSettings).order_by(pricing_settings_table.c.id).limit(1),
        )
        return result.scalars().first()
