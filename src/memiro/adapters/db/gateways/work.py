from dataclasses import asdict
from typing import override

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from memiro.adapters.db.tables import works_table
from memiro.application.common.gateway.work import WorkGateway, WorkRow
from memiro.entities.common.identifiers import WorkId


class SAWorkGateway(WorkGateway):
    """SQLAlchemy-based implementation of ``WorkGateway``."""

    def __init__(self, session: AsyncSession) -> None:
        """Keep the request-scoped session the gateway queries through."""
        self._session = session

    @override
    async def get(self, work_id: WorkId) -> WorkRow | None:
        """Read the row of one work: a work has no aggregate to hydrate."""
        row = (
            (await self._session.execute(select(works_table).where(works_table.c.id == work_id)))
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        # The columns of the table are the fields of the row: a work is stored
        # flat, and the mapping is what the migration and ``WorkRow`` agree on.
        return WorkRow(**row)

    @override
    async def add(self, work: WorkRow) -> None:
        """Insert the row of one work into the transaction the interactor commits."""
        await self._session.execute(insert(works_table).values(asdict(work)))

    @override
    async def replace(self, work: WorkRow) -> None:
        """Write the whole card over the stored row, its photo key included."""
        await self._session.execute(update(works_table).where(works_table.c.id == work.id).values(asdict(work)))

    @override
    async def remove(self, work_id: WorkId) -> None:
        """Delete the row of one work within the current transaction."""
        await self._session.execute(delete(works_table).where(works_table.c.id == work_id))

    @override
    async def holds_photo(self, key: str) -> bool:
        """Ask the column alone whether some work already names this photo."""
        result = await self._session.execute(select(works_table.c.id).where(works_table.c.photo_key == key))
        return result.first() is not None
