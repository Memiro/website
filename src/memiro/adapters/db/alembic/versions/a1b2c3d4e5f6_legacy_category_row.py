"""Give the legacy category the products were stamped with an actual row.

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-09-01
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 7a2d4e6f8b10 stamped every existing product with this identifier as the
# server default of the new products.category_id. The categories table was
# only created later, by f6a7b8c9d0e1, and empty — so on a populated database
# every one of those products points at a category that does not exist, and
# the storefront's catalogue, which inner-joins categories, comes out empty.
_LEGACY_CATEGORY_ID = "00000000-0000-0000-0000-000000000000"

# A placeholder the owner renames: the legacy MVP had no categories to carry
# over, so there is no true name to restore here.
_LEGACY_CATEGORY_NAME = "Зеркала"
_LEGACY_CATEGORY_SLUG = "mirrors"


def upgrade() -> None:
    """Apply the migration."""
    op.execute(
        text(
            """INSERT INTO categories (id, name, slug, sort_order, created_at, updated_at)
               SELECT CAST(:id AS uuid), :name, :slug, 0, now(), now()
               WHERE EXISTS (SELECT 1 FROM products WHERE category_id = CAST(:id AS uuid))
                 AND NOT EXISTS (SELECT 1 FROM categories WHERE id = CAST(:id AS uuid))"""
        ).bindparams(
            id=_LEGACY_CATEGORY_ID,
            name=_LEGACY_CATEGORY_NAME,
            slug=_LEGACY_CATEGORY_SLUG,
        )
    )


def downgrade() -> None:
    """Revert the migration."""
    # Only the untouched placeholder goes back: a category the owner has since
    # renamed or filled is his data, not this migration's to remove.
    op.execute(
        text(
            """DELETE FROM categories
               WHERE id = CAST(:id AS uuid) AND name = :name AND slug = :slug"""
        ).bindparams(
            id=_LEGACY_CATEGORY_ID,
            name=_LEGACY_CATEGORY_NAME,
            slug=_LEGACY_CATEGORY_SLUG,
        )
    )
