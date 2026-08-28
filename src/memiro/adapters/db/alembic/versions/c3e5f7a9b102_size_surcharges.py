"""Persist size-surcharge tiers and dictionary marking.

Revision ID: c3e5f7a9b102
Revises: 7a2d4e6f8b10
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3e5f7a9b102"
down_revision: str | None = "7a2d4e6f8b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.add_column(
        "attribute_values",
        sa.Column(
            "scaled_by_size_surcharge",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("attribute_values", "scaled_by_size_surcharge", server_default=None)
    op.create_table(
        "size_surcharges",
        sa.Column(
            "pricing_settings_id",
            sa.Uuid(),
            sa.ForeignKey("pricing_settings.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("from_long_side_mm", sa.Integer(), primary_key=True),
        sa.Column("factor", sa.Numeric(), nullable=False),
        sa.CheckConstraint("factor > 1", name="ck_size_surcharges_factor_above_one"),
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_table("size_surcharges")
    op.drop_column("attribute_values", "scaled_by_size_surcharge")
