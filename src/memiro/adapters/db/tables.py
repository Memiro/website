"""Tables of the domain and their imperative mapping — the one place both live.

Alembic autogenerate reads ``mapper_registry.metadata``, so importing this
module is what makes the domain tables exist for migrations and for the ORM
alike.
"""

from sqlalchemy import Boolean, CheckConstraint, Column, Enum, ForeignKey, Integer, Numeric, String, Table, Uuid
from sqlalchemy.orm import composite, relationship

from memiro.adapters.db.registry import mapper_registry
from memiro.adapters.db.types import AreaType, AttributeIdsType, MillimetersType, MoneyType
from memiro.entities.catalog.attribute.entity import Attribute, AttributeKind, AttributeValue
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.catalog.product.entity import ConfiguredValue, DeclaredValue, Product
from memiro.entities.pricing.pricing_settings import PricingSettings, SizeSurcharge

NAME_LENGTH = 255

attributes_table = Table(
    "attributes",
    mapper_registry.metadata,
    Column("id", Uuid(), primary_key=True),
    Column("category_id", Uuid(), nullable=False),
    Column("name", String(NAME_LENGTH), nullable=False),
    Column("kind", Enum(AttributeKind, name="attribute_kind", native_enum=False, length=NAME_LENGTH), nullable=False),
    Column("parent_ids", AttributeIdsType(), nullable=False),
    Column("is_customer_changeable", Boolean(), nullable=False),
    Column("sort_order", Integer(), nullable=False, default=0),
)

attribute_values_table = Table(
    "attribute_values",
    mapper_registry.metadata,
    Column("id", Uuid(), primary_key=True),
    Column("attribute_id", Uuid(), ForeignKey("attributes.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(NAME_LENGTH), nullable=False),
    Column("rate_amount", MoneyType(), nullable=False),
    Column("rate_unit", Enum(Unit, name="unit", native_enum=False, length=NAME_LENGTH), nullable=False),
    Column("scaled_by_shape", Boolean(), nullable=False, default=False),
    Column("scaled_by_size_surcharge", Boolean(), nullable=False, default=False),
    Column("marks_absence", Boolean(), nullable=False),
    Column("sort_order", Integer(), nullable=False, default=0),
    # The domain refuses a FACTOR of zero (it would annihilate the price
    # instead of scaling it); the database refuses it too, so no admin write
    # path can leave a row the calculation cannot use.
    CheckConstraint("rate_unit <> 'FACTOR' OR rate_amount > 0", name="ck_attribute_values_factor_is_positive"),
)

products_table = Table(
    "products",
    mapper_registry.metadata,
    Column("id", Uuid(), primary_key=True),
    Column("category_id", Uuid(), nullable=False),
    Column("name", String(NAME_LENGTH), nullable=False),
    Column("slug", String(NAME_LENGTH), nullable=False, unique=True),
    Column("is_published", Boolean(), nullable=False),
    Column("hides_calculated_price", Boolean(), nullable=False),
)

product_declared_values_table = Table(
    "product_declared_values",
    mapper_registry.metadata,
    Column("product_id", Uuid(), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("attribute_id", Uuid(), ForeignKey("attributes.id"), primary_key=True),
    Column("value_id", Uuid(), ForeignKey("attribute_values.id"), nullable=True),
    Column("quantity", Numeric(12, 4), nullable=True),
    # An unfinished declaration may name neither representation, but it can
    # never be a SELECT and NUMBER declaration at once. Attribute kind lives
    # in another table, so this is the strongest local check available.
    CheckConstraint(
        "value_id IS NULL OR quantity IS NULL",
        name="ck_product_declared_values_at_most_one_representation",
    ),
)

pricing_settings_table = Table(
    "pricing_settings",
    mapper_registry.metadata,
    Column("id", Uuid(), primary_key=True),
    Column("min_area", AreaType(), nullable=False),
    Column("min_order_total", MoneyType(), nullable=False),
    Column("max_long_side_mm", MillimetersType(), nullable=False),
    Column("max_short_side_mm", MillimetersType(), nullable=False),
)

size_surcharges_table = Table(
    "size_surcharges",
    mapper_registry.metadata,
    Column(
        "pricing_settings_id",
        Uuid(),
        ForeignKey("pricing_settings.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("from_long_side_mm", MillimetersType(), primary_key=True),
    Column("factor", Numeric(), nullable=False),
    CheckConstraint("factor > 1", name="ck_size_surcharges_factor_above_one"),
)

mapper_registry.map_imperatively(
    AttributeValue,
    attribute_values_table,
    properties={
        # The tariff is one value object over two columns; the money column
        # already deserializes into ``Money``, so the composite assembles the
        # ``Rate`` straight from mapped domain types.
        "rate": composite(Rate, attribute_values_table.c.rate_amount, attribute_values_table.c.rate_unit),
    },
)

mapper_registry.map_imperatively(
    Attribute,
    attributes_table,
    properties={
        "values": relationship(
            AttributeValue,
            lazy="raise_on_sql",
            order_by=(attribute_values_table.c.sort_order, attribute_values_table.c.id),
        ),
    },
)

mapper_registry.map_imperatively(
    DeclaredValue,
    product_declared_values_table,
    properties={
        "configured": composite(
            ConfiguredValue,
            product_declared_values_table.c.value_id,
            product_declared_values_table.c.quantity,
        ),
    },
)

mapper_registry.map_imperatively(
    Product,
    products_table,
    properties={
        "declared_values": relationship(DeclaredValue, lazy="raise_on_sql"),
    },
)

mapper_registry.map_imperatively(
    SizeSurcharge,
    size_surcharges_table,
    properties={
        "_pricing_settings_id": size_surcharges_table.c.pricing_settings_id,
        "_from_long_side_mm": size_surcharges_table.c.from_long_side_mm,
        "_factor": size_surcharges_table.c.factor,
    },
)

mapper_registry.map_imperatively(
    PricingSettings,
    pricing_settings_table,
    properties={
        "_size_surcharges": relationship(
            SizeSurcharge,
            cascade="all, delete-orphan",
            lazy="raise_on_sql",
            order_by=size_surcharges_table.c.from_long_side_mm,
        ),
    },
)
