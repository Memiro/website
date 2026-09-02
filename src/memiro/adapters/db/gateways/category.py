from typing import override

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memiro.adapters.db.tables import categories_table
from memiro.application.common.gateway.category import CategoryGateway
from memiro.entities.common.identifiers import CategoryId


class SACategoryGateway(CategoryGateway):
    """SQLAlchemy-based implementation of ``CategoryGateway``."""

    def __init__(self, session: AsyncSession) -> None:
        """Keep the request-scoped session the gateway queries through."""
        self._session = session

    @override
    async def exists(self, category_id: CategoryId) -> bool:
        """Ask the table for the identifier alone: no row of the section is needed here."""
        result = await self._session.execute(
            select(categories_table.c.id).where(categories_table.c.id == category_id),
        )
        return result.scalar_one_or_none() is not None
