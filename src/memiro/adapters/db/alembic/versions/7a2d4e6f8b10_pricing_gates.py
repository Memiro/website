"""Persist the customer pricing gates and numeric declarations.

Revision ID: 7a2d4e6f8b10
Revises: 9f1c0a3b7d21
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7a2d4e6f8b10"
down_revision: str | None = "9f1c0a3b7d21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME_LENGTH = 255


def upgrade() -> None:
    """Apply the migration."""
    op.add_column("attributes", sa.Column("category_id", sa.Uuid(), nullable=False))
    op.add_column(
        "attributes",
        sa.Column(
            "kind",
            sa.Enum("SELECT", "NUMBER", name="attribute_kind", native_enum=False, length=NAME_LENGTH),
            nullable=False,
        ),
    )
    op.add_column(
        "attributes",
        sa.Column("parent_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
    )
    op.add_column("attributes", sa.Column("is_customer_changeable", sa.Boolean(), nullable=False))
    op.add_column("attribute_values", sa.Column("marks_absence", sa.Boolean(), nullable=False))
    op.add_column("products", sa.Column("category_id", sa.Uuid(), nullable=False))
    op.add_column("products", sa.Column("is_published", sa.Boolean(), nullable=False))
    op.add_column("products", sa.Column("hides_calculated_price", sa.Boolean(), nullable=False))
    op.alter_column("product_declared_values", "value_id", existing_type=sa.Uuid(), nullable=True)
    op.add_column(
        "product_declared_values",
        sa.Column("quantity", sa.Numeric(precision=12, scale=4), nullable=True),
    )
    op.create_check_constraint(
        "ck_product_declared_values_at_most_one_representation",
        "product_declared_values",
        "value_id IS NULL OR quantity IS NULL",
    )
    op.add_column("pricing_settings", sa.Column("max_long_side_mm", sa.Integer(), nullable=False))
    op.add_column("pricing_settings", sa.Column("max_short_side_mm", sa.Integer(), nullable=False))


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column("pricing_settings", "max_short_side_mm")
    op.drop_column("pricing_settings", "max_long_side_mm")
    op.drop_constraint(
        "ck_product_declared_values_at_most_one_representation",
        "product_declared_values",
        type_="check",
    )
    op.drop_column("product_declared_values", "quantity")
    op.alter_column("product_declared_values", "value_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("products", "hides_calculated_price")
    op.drop_column("products", "is_published")
    op.drop_column("products", "category_id")
    op.drop_column("attribute_values", "marks_absence")
    op.drop_column("attributes", "is_customer_changeable")
    op.drop_column("attributes", "parent_ids")
    op.drop_column("attributes", "kind")
    op.drop_column("attributes", "category_id")
