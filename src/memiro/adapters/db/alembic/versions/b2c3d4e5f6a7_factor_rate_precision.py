"""Widen the rate column so a FACTOR multiplier is not rounded to kopecks.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    # attribute_values.rate_amount holds money for every unit but FACTOR, where
    # it holds a multiplier. At Numeric(12, 2) a shape factor of 1.125 was
    # stored as 1.13 and round mirrors drifted from the workbook; below 0.005 it
    # rounded to zero and tripped ck_attribute_values_factor_is_positive.
    op.alter_column(
        "attribute_values",
        "rate_amount",
        existing_type=sa.Numeric(precision=12, scale=2),
        type_=sa.Numeric(precision=12, scale=4),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Revert the migration."""
    op.alter_column(
        "attribute_values",
        "rate_amount",
        existing_type=sa.Numeric(precision=12, scale=4),
        type_=sa.Numeric(precision=12, scale=2),
        existing_nullable=False,
    )
