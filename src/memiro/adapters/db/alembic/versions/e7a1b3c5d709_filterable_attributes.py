"""Give the owner back the switch that keeps an attribute out of the filters.

Revision ID: e7a1b3c5d709
Revises: d6e8f0a2b431
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7a1b3c5d709"
down_revision: str | None = "d6e8f0a2b431"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    # Existing attributes keep building filters, which is what the storefront
    # did before the switch existed; the owner takes out what narrows nothing.
    op.add_column("attributes", sa.Column("is_filterable", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.alter_column("attributes", "is_filterable", server_default=None)


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column("attributes", "is_filterable")
