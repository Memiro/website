"""Tables the price of a configuration is calculated from.

Revision ID: 9f1c0a3b7d21
Revises:
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f1c0a3b7d21"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME_LENGTH = 255


def upgrade() -> None:
    """Apply the migration."""
    op.create_table(
        "attributes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=NAME_LENGTH), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "attribute_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attribute_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=NAME_LENGTH), nullable=False),
        sa.Column("rate_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "rate_unit",
            sa.Enum(
                "PIECE",
                "LINEAR_METER",
                "SQUARE_METER",
                "FACTOR",
                name="unit",
                native_enum=False,
                length=NAME_LENGTH,
            ),
            nullable=False,
        ),
        sa.Column("scaled_by_shape", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["attribute_id"], ["attributes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "rate_unit <> 'FACTOR' OR rate_amount > 0",
            name="ck_attribute_values_factor_is_positive",
        ),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=NAME_LENGTH), nullable=False),
        sa.Column("slug", sa.String(length=NAME_LENGTH), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "product_declared_values",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("attribute_id", sa.Uuid(), nullable=False),
        sa.Column("value_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attribute_id"], ["attributes.id"]),
        sa.ForeignKeyConstraint(["value_id"], ["attribute_values.id"]),
        sa.PrimaryKeyConstraint("product_id", "attribute_id"),
    )
    op.create_table(
        "pricing_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("min_area", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("min_order_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_table("pricing_settings")
    op.drop_table("product_declared_values")
    op.drop_table("products")
    op.drop_table("attribute_values")
    op.drop_table("attributes")
