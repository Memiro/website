from typing import override
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memiro.adapters.db.tables import seller_requisites_table, site_contacts_table
from memiro.application.common.gateway.site import SiteGateway
from memiro.application.read_site.models import ContactsModel, RequisiteModel

# The site has exactly one row of each, fetched by identifier rather than by
# "whatever the table holds": a stray second row must not be able to rename
# the studio or the seller.
SITE_CONTACTS_ID = UUID("0197c0de-0000-7000-8000-000000000002")
SELLER_REQUISITES_ID = UUID("0197c0de-0000-7000-8000-000000000003")

# The caption each requisite is printed under; the seller's own name carries
# none — it reads as the name of the seller.
REQUISITE_LABELS: tuple[tuple[str, str], ...] = (
    ("name", ""),
    ("ogrn", "ОГРН/ОГРНИП"),
    ("inn", "ИНН"),
    ("address", "Адрес"),
)


class SASiteGateway(SiteGateway):
    """SQLAlchemy projections of the site's own data."""

    def __init__(self, session: AsyncSession) -> None:
        """Keep the request-scoped session the projections execute through."""
        self._session = session

    @override
    async def read_contacts(self) -> ContactsModel | None:
        """Read the single row of studio contacts."""
        row = (
            (
                await self._session.execute(
                    select(site_contacts_table).where(site_contacts_table.c.id == SITE_CONTACTS_ID)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return ContactsModel(
            city=row["city"],
            street=row["street"],
            phone=row["phone"],
            phone_display=row["phone_display"],
            email=row["email"],
            hours=row["hours"],
            max_link=row["max_link"],
            telegram=row["telegram"],
            vk=row["vk"],
            map_embed=row["map_embed"],
        )

    @override
    async def read_seller_requisites(self) -> list[RequisiteModel]:
        """Read the requisites the owner has filled; an empty one is not printed."""
        row = (
            (
                await self._session.execute(
                    select(seller_requisites_table).where(seller_requisites_table.c.id == SELLER_REQUISITES_ID)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return []
        return [RequisiteModel(label=label, value=row[column]) for column, label in REQUISITE_LABELS if row[column]]
