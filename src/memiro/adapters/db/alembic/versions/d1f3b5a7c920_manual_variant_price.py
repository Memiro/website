"""Remember that a variant price was typed by the owner.

Revision ID: d1f3b5a7c920
Revises: c8e0a2b4d631
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1f3b5a7c920"
down_revision: str | None = "c8e0a2b4d631"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.add_column(
        "product_variants",
        sa.Column("price_is_manual", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("product_variants", "price_is_manual", server_default=None)


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column("product_variants", "price_is_manual")
