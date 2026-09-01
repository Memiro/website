"""Drop the consent flag: consent is now a precondition of the inquiry itself.

Revision ID: c5d6e7f8a9b0
Revises: b2c3d4e5f6a7
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    # An inquiry cannot be built without consent, so the column could only ever
    # hold true and stored nothing; the accepted revision stays in
    # consent_version, which is what the consent has to prove. Dropping a column
    # of legal meaning is destructive: the owner confirmed it on 2026-09-01 (§0).
    op.drop_column("inquiries", "consent")


def downgrade() -> None:
    """Revert the migration."""
    op.add_column(
        "inquiries",
        sa.Column("consent", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("inquiries", "consent", server_default=None)
