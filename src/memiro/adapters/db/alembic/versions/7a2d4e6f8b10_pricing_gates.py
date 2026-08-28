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
_LEGACY_CATEGORY_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    """Apply the migration."""
    op.add_column(
        "attributes",
        sa.Column(
            "category_id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text(f"'{_LEGACY_CATEGORY_ID}'::uuid"),
        ),
    )
    op.add_column(
        "attributes",
        sa.Column(
            "kind",
            sa.Enum("SELECT", "NUMBER", name="attribute_kind", native_enum=False, length=NAME_LENGTH),
            nullable=False,
            server_default=sa.text("'SELECT'"),
        ),
    )
    op.add_column(
        "attributes",
        sa.Column(
            "parent_ids",
            postgresql.ARRAY(sa.Uuid()),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
    )
    op.add_column(
        "attributes",
        sa.Column("is_customer_changeable", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "attribute_values",
        sa.Column("marks_absence", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "products",
        sa.Column(
            "category_id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text(f"'{_LEGACY_CATEGORY_ID}'::uuid"),
        ),
    )
    op.add_column(
        "products",
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "products",
        sa.Column("hides_calculated_price", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
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
    op.add_column(
        "pricing_settings",
        sa.Column("max_long_side_mm", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "pricing_settings",
        sa.Column("max_short_side_mm", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    for table_name, column_name in (
        ("attributes", "category_id"),
        ("attributes", "kind"),
        ("attributes", "parent_ids"),
        ("attributes", "is_customer_changeable"),
        ("attribute_values", "marks_absence"),
        ("products", "category_id"),
        ("products", "is_published"),
        ("products", "hides_calculated_price"),
        ("pricing_settings", "max_long_side_mm"),
        ("pricing_settings", "max_short_side_mm"),
    ):
        op.alter_column(table_name, column_name, server_default=None)


def downgrade() -> None:
    """Revert the migration."""
    has_unrepresentable_declarations = (
        op.get_bind()
        .execute(
            sa.text("SELECT EXISTS (SELECT 1 FROM product_declared_values WHERE value_id IS NULL)"),
        )
        .scalar_one()
    )
    if has_unrepresentable_declarations:
        msg = "Cannot downgrade pricing gates while declarations without value_id exist"
        raise RuntimeError(msg)

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
