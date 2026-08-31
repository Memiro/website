"""Add category and product-card read storage.

Revision ID: f6a7b8c9d0e1
Revises: e5f9c1d2a324
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f9c1d2a324"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.add_column("products", sa.Column("description", sa.String(2000), server_default="", nullable=False))
    op.alter_column("products", "description", server_default=None)
    op.create_table(
        "product_images",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("product_id", "key"),
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_table("product_images")
    op.drop_column("products", "description")
    op.drop_table("categories")
