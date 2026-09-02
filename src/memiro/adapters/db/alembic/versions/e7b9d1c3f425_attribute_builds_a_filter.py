"""Give the attribute the flag that says it builds a catalogue filter.

Revision ID: e7b9d1c3f425
Revises: d6e8f0a2b431
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7b9d1c3f425"
down_revision: str | None = "d6e8f0a2b431"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    # Every attribute that predates the flag keeps the catalogue as it is: the
    # owner turns filtering on one attribute at a time, and the temporary
    # default goes away so no later insert can dodge the decision.
    op.add_column("attributes", sa.Column("is_filterable", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.alter_column("attributes", "is_filterable", server_default=None)


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column("attributes", "is_filterable")
