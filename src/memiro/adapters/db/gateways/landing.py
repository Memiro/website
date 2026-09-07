from collections.abc import Collection, Sequence
from typing import override

from sqlalchemy import ColumnElement, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from memiro.adapters.db.errors import LOCK_NOT_AVAILABLE, LockTimeoutError, sqlstate_of
from memiro.adapters.db.tables import landing_conditions_table, landings_table
from memiro.application.common.gateway.landing import LandingGateway
from memiro.entities.catalog.landing.entity import Landing
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, LandingId


class SALandingGateway(LandingGateway):
    """SQLAlchemy-based implementation of ``LandingGateway``."""

    def __init__(self, session: AsyncSession) -> None:
        """Keep the request-scoped session the gateway queries through."""
        self._session = session

    @override
    async def get(self, landing_id: LandingId, *, for_update: bool = False) -> Landing | None:
        """Load one landing with the narrowing its commands replace whole."""
        statement = (
            select(Landing)
            .where(landings_table.c.id == landing_id)
            .options(
                # Imperative mapping leaves the instrumented attributes invisible
                # to the type checkers; the relationship exists at runtime.
                selectinload(Landing._conditions),  # type: ignore[arg-type]  # noqa: SLF001  # pyright: ignore[reportArgumentType,reportPrivateUsage]
            )
        )
        if for_update:
            statement = statement.with_for_update(of=landings_table)
        try:
            result = await self._session.execute(statement)
        except DBAPIError as error:
            # A refused lock is a lost race, not a defect: the caller is told
            # to retry (429), while every other driver failure stays a 500.
            if sqlstate_of(error) != LOCK_NOT_AVAILABLE:
                raise
            raise LockTimeoutError from error
        return result.scalar_one_or_none()

    @override
    async def slug_owner(self, slug: str) -> LandingId | None:
        """Ask the unique column who holds the address: no aggregate is needed to answer that."""
        return (
            await self._session.execute(select(landings_table.c.id).where(landings_table.c.slug == slug))
        ).scalar_one_or_none()

    @override
    async def headings_narrowing_by_values(self, value_ids: Collection[AttributeValueId]) -> Sequence[str]:
        """Name the landings that narrow by any of these rows, each once, in one stable order."""
        if not value_ids:
            return []
        return await self._headings(landing_conditions_table.c.value_id.in_(value_ids))

    @override
    async def headings_narrowing_by_attribute(self, attribute_id: AttributeId) -> Sequence[str]:
        """Name the landings that narrow by anything of this attribute, in one stable order."""
        return await self._headings(landing_conditions_table.c.attribute_id == attribute_id)

    async def _headings(self, narrowing: ColumnElement[bool]) -> Sequence[str]:
        """Read the headings of the landings one narrowing condition names."""
        rows = (
            await self._session.execute(
                select(landings_table.c.heading)
                .select_from(
                    landings_table.join(
                        landing_conditions_table,
                        landing_conditions_table.c.landing_id == landings_table.c.id,
                    )
                )
                .where(narrowing)
                .distinct()
                .order_by(landings_table.c.heading)
            )
        ).scalars()
        return list(rows)
