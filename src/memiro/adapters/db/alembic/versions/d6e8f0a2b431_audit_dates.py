"""Give the catalogue aggregates the audit dates their entity pages promise.

Revision ID: d6e8f0a2b431
Revises: c5d6e7f8a9b0
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6e8f0a2b431"
down_revision: str | None = "c5d6e7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The rows that predate the columns were created at some unrecorded past
# moment; the honest backfill is the instant they acquired a date, and it
# keeps the columns non-null from the first day.
_AUDIT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("attributes", "created_at"),
    ("attributes", "updated_at"),
    ("products", "created_at"),
    ("products", "updated_at"),
    ("pricing_settings", "updated_at"),
)


def upgrade() -> None:
    """Apply the migration."""
    for table, column in _AUDIT_COLUMNS:
        op.add_column(
            table,
            sa.Column(column, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.alter_column(table, column, server_default=None)


def downgrade() -> None:
    """Revert the migration."""
    for table, column in reversed(_AUDIT_COLUMNS):
        op.drop_column(table, column)
