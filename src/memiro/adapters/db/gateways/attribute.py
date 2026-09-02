from collections.abc import Sequence
from typing import override

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from memiro.adapters.db.errors import LOCK_NOT_AVAILABLE, LockTimeoutError, sqlstate_of
from memiro.adapters.db.tables import attributes_table
from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.common.identifiers import AttributeId


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

    @override
    async def get(self, attribute_id: AttributeId, *, for_update: bool = False) -> Attribute | None:
        """Load one attribute with the values of its dictionary, locking the root on demand."""
        statement = (
            select(Attribute).where(attributes_table.c.id == attribute_id).options(selectinload(Attribute.values))  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
        )
        if for_update:
            # The lock is taken on the root alone: the children follow their
            # parent, and locking them would deadlock two owners editing two
            # dictionaries that share nothing.
            statement = statement.with_for_update(of=attributes_table)
        try:
            result = await self._session.execute(statement)
        except DBAPIError as error:
            if sqlstate_of(error) != LOCK_NOT_AVAILABLE:
                raise
            raise LockTimeoutError from error
        return result.scalar_one_or_none()
