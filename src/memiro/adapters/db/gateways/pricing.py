from typing import override

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from memiro.adapters.db.tables import pricing_settings_table
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.entities.pricing.pricing_settings import PRICING_SETTINGS_ID, PricingSettings


class SAPricingSettingsGateway(PricingSettingsGateway):
    """SQLAlchemy-based implementation of ``PricingSettingsGateway``."""

    def __init__(self, session: AsyncSession) -> None:
        """Keep the request-scoped session the gateway queries through."""
        self._session = session

    @override
    async def get_with_surcharges(self) -> PricingSettings | None:
        """Load the settings and its ordered tiers by the site's known id."""
        result = await self._session.execute(
            select(PricingSettings)
            .where(pricing_settings_table.c.id == PRICING_SETTINGS_ID)
            # The mutable relationship stays private; consumers receive the
            # aggregate's immutable tuple property instead (§6.2).
            .options(
                selectinload(PricingSettings._size_surcharges),  # type: ignore[arg-type]  # noqa: SLF001  # pyright: ignore[reportAttributeAccessIssue]
            ),
        )
        return result.scalar_one_or_none()
