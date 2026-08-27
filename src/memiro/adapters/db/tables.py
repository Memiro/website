"""Tables of the domain and their imperative mapping — the one place both live.

Alembic autogenerate reads ``mapper_registry.metadata``, so importing this
module is what makes the domain tables exist for migrations and for the ORM
alike.
"""

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, String, Table, Uuid
from sqlalchemy.orm import composite, relationship

from memiro.adapters.db.registry import mapper_registry
from memiro.adapters.db.types import AreaType, MoneyType
from memiro.entities.catalog.attribute.entity import Attribute, AttributeValue
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.catalog.product.entity import DeclaredValue, Product
from memiro.entities.pricing.pricing_settings import PricingSettings

NAME_LENGTH = 255

attributes_table = Table(
    "attributes",
    mapper_registry.metadata,
    Column("id", Uuid(), primary_key=True),
    Column("name", String(NAME_LENGTH), nullable=False),
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
    Column("sort_order", Integer(), nullable=False, default=0),
)

products_table = Table(
    "products",
    mapper_registry.metadata,
    Column("id", Uuid(), primary_key=True),
    Column("name", String(NAME_LENGTH), nullable=False),
    Column("slug", String(NAME_LENGTH), nullable=False, unique=True),
)

product_declared_values_table = Table(
    "product_declared_values",
    mapper_registry.metadata,
    Column("product_id", Uuid(), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("attribute_id", Uuid(), ForeignKey("attributes.id"), primary_key=True),
    Column("value_id", Uuid(), ForeignKey("attribute_values.id"), nullable=False),
)

pricing_settings_table = Table(
    "pricing_settings",
    mapper_registry.metadata,
    Column("id", Uuid(), primary_key=True),
    Column("min_area", AreaType(), nullable=False),
    Column("min_order_total", MoneyType(), nullable=False),
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
            order_by=attribute_values_table.c.sort_order,
        ),
    },
)

mapper_registry.map_imperatively(
    DeclaredValue,
    product_declared_values_table,
)

mapper_registry.map_imperatively(
    Product,
    products_table,
    properties={
        "declared_values": relationship(DeclaredValue, lazy="raise_on_sql"),
    },
)

mapper_registry.map_imperatively(PricingSettings, pricing_settings_table)
