from typing import override

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from memiro.adapters.db.tables import inquiries_table
from memiro.application.common.gateway.inquiry import InquiryGateway
from memiro.entities.common.identifiers import InquiryId
from memiro.entities.inquiry.entity import Inquiry


class SAInquiryGateway(InquiryGateway):
    """SQLAlchemy-based implementation of ``InquiryGateway``."""

    def __init__(self, session: AsyncSession) -> None:
        """Keep the request-scoped session the gateway queries through."""
        self._session = session

    @override
    async def get(self, inquiry_id: InquiryId) -> Inquiry | None:
        """Load one inquiry together with its immutable item snapshots."""
        result = await self._session.execute(
            select(Inquiry).where(inquiries_table.c.id == inquiry_id).options(selectinload(Inquiry._items)),  # type: ignore[arg-type, misc]  # noqa: SLF001  # pyright: ignore[reportArgumentType,reportPrivateUsage]
        )
        return result.scalar_one_or_none()
