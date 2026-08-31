from collections.abc import Sequence
from typing import override

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from memiro.adapters.db.tables import attributes_table
from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.entities.catalog.attribute.entity import Attribute


class SAAttributeGateway(AttributeGateway):
    """SQLAlchemy-based implementation of ``AttributeGateway``."""

    def __init__(self, session: AsyncSession) -> None:
        """Keep the request-scoped session the gateway queries through."""
        self._session = session

    @override
    async def list_with_values(self) -> Sequence[Attribute]:
        """Load the whole dictionary, each attribute with its values in the owner's order."""
        result = await self._session.execute(
            # Imperative mapping leaves the instrumented attribute invisible
            # to the type checkers; the relationship exists at runtime.
            select(Attribute).order_by(attributes_table.c.sort_order).options(selectinload(Attribute.values)),  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
        )
        return result.scalars().all()
