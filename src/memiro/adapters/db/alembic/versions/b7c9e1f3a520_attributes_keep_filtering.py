"""Let the attributes that predate the sidebar keep building filters.

Revision ID: b7c9e1f3a520
Revises: a9c3e5f7b120
Create Date: 2026-09-07
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "b7c9e1f3a520"
down_revision: str | None = "a9c3e5f7b120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    # ``e7b9d1c3f425`` added the switch off, because nothing read it yet: the
    # sidebar it gates lands with this revision. Off for every existing row
    # would mean a catalogue that narrows by nothing until the owner clicks
    # through the whole dictionary, so the storefront keeps the behaviour it
    # had before the switch existed and the owner takes out what narrows
    # nothing.
    op.execute(text("UPDATE attributes SET is_filterable = true"))


def downgrade() -> None:
    """Revert the migration."""
    op.execute(text("UPDATE attributes SET is_filterable = false"))
