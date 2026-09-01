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


def _stamp(table: str, column: str) -> None:
    """Add one audit column and backfill the rows that predate it."""
    # The rows were created at some moment nothing recorded; the honest
    # backfill is the instant they acquired a date, and the temporary default
    # goes away so no later insert can dodge the domain clock.
    op.add_column(table, sa.Column(column, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.alter_column(table, column, server_default=None)


def upgrade() -> None:
    """Apply the migration."""
    _stamp("attributes", "created_at")
    _stamp("attributes", "updated_at")
    _stamp("products", "created_at")
    _stamp("products", "updated_at")
    _stamp("pricing_settings", "updated_at")


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column("pricing_settings", "updated_at")
    op.drop_column("products", "updated_at")
    op.drop_column("products", "created_at")
    op.drop_column("attributes", "updated_at")
    op.drop_column("attributes", "created_at")
