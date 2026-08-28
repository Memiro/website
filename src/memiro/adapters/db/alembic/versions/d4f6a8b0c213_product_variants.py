"""Persist product variants and their derived product price.

Revision ID: d4f6a8b0c213
Revises: c3e5f7a9b102
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4f6a8b0c213"
down_revision: str | None = "c3e5f7a9b102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.add_column(
        "products",
        sa.Column("price_from", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.create_table(
        "product_variants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("width_mm", sa.Integer(), nullable=False),
        sa.Column("height_mm", sa.Integer(), nullable=False),
        sa.Column("overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_product_variants_sort_order_non_negative",
        ),
        sa.UniqueConstraint(
            "product_id",
            "fingerprint",
            name="uq_product_variants_product_fingerprint",
        ),
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_table("product_variants")
    op.drop_column("products", "price_from")
