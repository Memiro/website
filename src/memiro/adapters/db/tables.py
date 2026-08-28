"""Tables of the domain and their imperative mapping — the one place both live.

Alembic autogenerate reads ``mapper_registry.metadata``, so importing this
module is what makes the domain tables exist for migrations and for the ORM
alike.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    UniqueConstraint,
    Uuid,
    event,
)
from sqlalchemy.orm import composite, relationship

from memiro.adapters.db.registry import mapper_registry
from memiro.adapters.db.types import AreaType, AttributeIdsType, MillimetersType, MoneyType, VariantOverridesType
from memiro.entities.catalog.attribute.entity import Attribute, AttributeKind, AttributeValue
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.catalog.product.entity import ConfiguredValue, DeclaredValue, Product, Variant
from memiro.entities.common.measure import Dimensions
from memiro.entities.pricing.pricing_settings import PricingSettings, SizeSurcharge

NAME_LENGTH = 255


def _ensure_variant_fingerprint(variant: Variant, _context: object) -> None:
    """Recheck the derived database guard after SQLAlchemy hydration."""
    variant.ensure_stored_fingerprint()


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
    Column("price_from", MoneyType(), nullable=True),
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

product_variants_table = Table(
    "product_variants",
    mapper_registry.metadata,
    Column("id", Uuid(), primary_key=True),
    Column("product_id", Uuid(), ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
    Column("width_mm", MillimetersType(), nullable=False),
    Column("height_mm", MillimetersType(), nullable=False),
    Column("overrides", VariantOverridesType(), nullable=False),
    Column("price", MoneyType(), nullable=False),
    Column("sort_order", Integer(), nullable=False),
    Column("fingerprint", Uuid(), nullable=False),
    CheckConstraint("sort_order >= 0", name="ck_product_variants_sort_order_non_negative"),
    UniqueConstraint("product_id", "fingerprint", name="uq_product_variants_product_fingerprint"),
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
    Variant,
    product_variants_table,
    properties={
        "_dimensions": composite(
            Dimensions,
            product_variants_table.c.width_mm,
            product_variants_table.c.height_mm,
        ),
        "_fingerprint": product_variants_table.c.fingerprint,
        "_overrides": product_variants_table.c.overrides,
        "_price": product_variants_table.c.price,
        "_sort_order": product_variants_table.c.sort_order,
    },
)
event.listen(Variant, "load", _ensure_variant_fingerprint)

mapper_registry.map_imperatively(
    Product,
    products_table,
    properties={
        "_price_from": products_table.c.price_from,
        "declared_values": relationship(DeclaredValue, lazy="raise_on_sql"),
        "_variants": relationship(
            Variant,
            cascade="all, delete-orphan",
            lazy="raise_on_sql",
            order_by=(product_variants_table.c.sort_order, product_variants_table.c.id),
        ),
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
