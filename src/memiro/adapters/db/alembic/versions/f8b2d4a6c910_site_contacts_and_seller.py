"""Make the studio contacts and the seller requisites data instead of code.

Revision ID: f8b2d4a6c910
Revises: e7a1b3c5d709
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "f8b2d4a6c910"
down_revision: str | None = "e7a1b3c5d709"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTACTS_ID = "0197c0de-0000-7000-8000-000000000002"
_SELLER_ID = "0197c0de-0000-7000-8000-000000000003"

# The contacts the storefront already printed, moved out of the markup that
# carried them. The seller row is born empty: a wrong OGRN is worse than a
# missing one, and the owner fills it before the site goes live.
_CONTACTS = {
    "city": "Санкт-Петербург",
    "street": "Александра Матросова, 4к2ж",
    "phone": "+79812304050",
    "phone_display": "+7 981 230-40-50",
    "email": "memiro.ru@yandex.ru",
    "hours": "Ежедневно, по предварительной записи",
    "max_link": "",
    "telegram": "https://t.me/memiro_shop",
    "vk": "https://vk.com/memirospb",
    "map_embed": (
        "https://yandex.ru/map-widget/v1/?um=constructor%3A"
        "0d49dffecadc7ce7a218e08a0b62b35502b15e05faa72ecea01c3be9dea4a3f1"
        "&source=constructor"
    ),
}


def upgrade() -> None:
    """Apply the migration."""
    op.create_table(
        "site_contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("city", sa.String(255), nullable=False),
        sa.Column("street", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(255), nullable=False),
        sa.Column("phone_display", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hours", sa.String(255), nullable=False),
        sa.Column("max_link", sa.String(255), nullable=False),
        sa.Column("telegram", sa.String(255), nullable=False),
        sa.Column("vk", sa.String(255), nullable=False),
        sa.Column("map_embed", sa.String(1000), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "seller_requisites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ogrn", sa.String(255), nullable=False),
        sa.Column("inn", sa.String(255), nullable=False),
        sa.Column("address", sa.String(255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        text(
            """INSERT INTO site_contacts
               (id, city, street, phone, phone_display, email, hours,
                max_link, telegram, vk, map_embed, updated_at)
               VALUES (CAST(:id AS uuid), :city, :street, :phone, :phone_display, :email, :hours,
                       :max_link, :telegram, :vk, :map_embed, now())"""
        ).bindparams(id=_CONTACTS_ID, **_CONTACTS)
    )
    op.execute(
        text(
            """INSERT INTO seller_requisites (id, name, ogrn, inn, address, updated_at)
               VALUES (CAST(:id AS uuid), '', '', '', '', now())"""
        ).bindparams(id=_SELLER_ID)
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_table("seller_requisites")
    op.drop_table("site_contacts")
