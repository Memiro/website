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
        return WorkRow(
            id=row["id"],
            photo_key=row["photo_key"],
            product_id=row["product_id"],
            title=row["title"],
            description=row["description"],
            is_published=row["is_published"],
            sort_order=row["sort_order"],
        )

    @override
    async def add(self, work: WorkRow) -> None:
        """Insert the row of one work into the transaction the interactor commits."""
        await self._session.execute(insert(works_table).values(_columns(work)))

    @override
    async def replace(self, work: WorkRow) -> None:
        """Write the whole card over the stored row, its photo key included."""
        await self._session.execute(update(works_table).where(works_table.c.id == work.id).values(_columns(work)))

    @override
    async def remove(self, work_id: WorkId) -> None:
        """Delete the row of one work within the current transaction."""
        await self._session.execute(delete(works_table).where(works_table.c.id == work_id))

    @override
    async def holds_photo(self, key: str) -> bool:
        """Ask the column alone whether some work already names this photo."""
        result = await self._session.execute(select(works_table.c.id).where(works_table.c.photo_key == key))
        return result.first() is not None


def _columns(work: WorkRow) -> dict[str, object]:
    """Spell one work in the columns that store it."""
    return {
        "id": work.id,
        "photo_key": work.photo_key,
        "product_id": work.product_id,
        "title": work.title,
        "description": work.description,
        "is_published": work.is_published,
        "sort_order": work.sort_order,
    }
