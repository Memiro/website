"""Let a product go and leave the inquiry position its own names.

Revision ID: b4d6f8a0c235
Revises: e7b9d1c3f425
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4d6f8a0c235"
down_revision: str | None = "e7b9d1c3f425"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FOREIGN_KEY = "inquiry_items_product_id_fkey"


def upgrade() -> None:
    """Apply the migration."""
    # The snapshot is not a reference: the position keeps the name and the
    # numbers it was taken with, and the owner is free to remove the product
    # a year later (docs/entities/inquiry.md, rule 5).
    op.alter_column("inquiry_items", "product_id", existing_type=sa.Uuid(), nullable=True)
    op.drop_constraint(FOREIGN_KEY, "inquiry_items", type_="foreignkey")
    op.create_foreign_key(FOREIGN_KEY, "inquiry_items", "products", ["product_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    """Revert the migration."""
    op.drop_constraint(FOREIGN_KEY, "inquiry_items", type_="foreignkey")
    op.create_foreign_key(FOREIGN_KEY, "inquiry_items", "products", ["product_id"], ["id"])
    op.alter_column("inquiry_items", "product_id", existing_type=sa.Uuid(), nullable=False)
