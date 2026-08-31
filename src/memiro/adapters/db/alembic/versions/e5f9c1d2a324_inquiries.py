"""Persist inquiry aggregates and immutable item snapshots.

Revision ID: e5f9c1d2a324
Revises: d4f6a8b0c213
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5f9c1d2a324"
down_revision: str | None = "d4f6a8b0c213"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME_LENGTH = 255


def upgrade() -> None:
    """Apply the migration."""
    op.create_table(
        "inquiries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "SELECTION", "FREE_FORM", "PRODUCT_CARD", name="inquiry_source", native_enum=False, length=NAME_LENGTH
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=NAME_LENGTH), nullable=False),
        sa.Column("phone", sa.String(length=NAME_LENGTH), nullable=False),
        sa.Column("email", sa.String(length=NAME_LENGTH), nullable=True),
        sa.Column("comment", sa.String(length=2_000), nullable=False),
        sa.Column("consent", sa.Boolean(), nullable=False),
        sa.Column("consent_version", sa.String(length=NAME_LENGTH), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "inquiry_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("inquiry_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("product_name", sa.String(length=NAME_LENGTH), nullable=False),
        sa.Column("price_from", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("calculated_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "verdict",
            sa.Enum(
                "PRICED",
                "HIDDEN",
                "BEYOND_LIMITS",
                "NOT_PRICEABLE",
                name="pricing_verdict",
                native_enum=False,
                length=NAME_LENGTH,
            ),
            nullable=False,
        ),
        sa.Column("wish", sa.String(length=1_000), nullable=False),
        sa.ForeignKeyConstraint(["inquiry_id"], ["inquiries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_table("inquiry_items")
    op.drop_table("inquiries")
