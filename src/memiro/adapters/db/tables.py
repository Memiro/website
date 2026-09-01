"""Tables of the domain and their imperative mapping — the one place both live.

Alembic autogenerate reads ``mapper_registry.metadata``, so importing this
module is what makes the domain tables exist for migrations and for the ORM
alike.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
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
from memiro.adapters.db.types import (
    AreaType,
    AttributeIdsType,
    InquiryConfigurationType,
    MillimetersType,
    MoneyType,
    PhoneType,
    RateAmountType,
    VariantOverridesType,
)
from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.catalog.attribute.entity import Attribute, AttributeKind, AttributeValue
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.catalog.product.entity import DeclaredValue, Product, Variant
from memiro.entities.common.measure import Dimensions
from memiro.entities.inquiry.consent import Consent
from memiro.entities.inquiry.entity import (
    Inquiry,
    InquiryItem,
    InquirySource,
    ensure_the_snapshot_agrees_with_its_verdict,
)
from memiro.entities.pricing.pricing_settings import PricingSettings, SizeSurcharge
from memiro.entities.pricing.quotation import PricingVerdict

NAME_LENGTH = 255


def _ensure_item_snapshot(item: InquiryItem, _context: object) -> None:
    """Recheck the snapshot invariant after hydration: the ORM builds a row past ``__init__`` (§8.5)."""
    ensure_the_snapshot_agrees_with_its_verdict(item.verdict, item.calculated_price, item.configuration)


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
    Column("rate_amount", RateAmountType(), nullable=False),
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
    Column("description", String(2_000), nullable=False),
    Column("is_published", Boolean(), nullable=False),
    Column("hides_calculated_price", Boolean(), nullable=False),
    Column("price_from", MoneyType(), nullable=True),
)

categories_table = Table(
    "categories",
    mapper_registry.metadata,
    Column("id", Uuid(), primary_key=True),
    Column("name", String(NAME_LENGTH), nullable=False),
    Column("slug", String(NAME_LENGTH), nullable=False, unique=True),
    Column("sort_order", Integer(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
product_images_table = Table(
    "product_images",
    mapper_registry.metadata,
    Column("product_id", Uuid(), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("key", String(NAME_LENGTH), primary_key=True),
    Column("sort_order", Integer(), nullable=False),
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

inquiries_table = Table(
    "inquiries",
    mapper_registry.metadata,
    Column("id", Uuid(), primary_key=True),
    Column("source", Enum(InquirySource, name="inquiry_source", native_enum=False, length=NAME_LENGTH), nullable=False),
    Column("name", String(NAME_LENGTH), nullable=False),
    Column("phone", PhoneType(NAME_LENGTH), nullable=False),
    Column("email", String(NAME_LENGTH), nullable=True),
    Column("comment", String(2_000), nullable=False),
    Column("consent_version", String(NAME_LENGTH), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

inquiry_items_table = Table(
    "inquiry_items",
    mapper_registry.metadata,
    Column("id", Uuid(), primary_key=True),
    Column("inquiry_id", Uuid(), ForeignKey("inquiries.id", ondelete="CASCADE"), nullable=False),
    Column("product_id", Uuid(), ForeignKey("products.id"), nullable=False),
    Column("product_name", String(NAME_LENGTH), nullable=False),
    Column("price_from", MoneyType(), nullable=True),
    Column("configuration", InquiryConfigurationType(), nullable=True),
    Column("calculated_price", MoneyType(), nullable=True),
    Column(
        "verdict",
        Enum(PricingVerdict, name="pricing_verdict", native_enum=False, length=NAME_LENGTH),
        nullable=False,
    ),
    Column("wish", String(1_000), nullable=False),
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
    InquiryItem,
    inquiry_items_table,
    properties={
        "configuration": inquiry_items_table.c.configuration,
    },
)
event.listen(InquiryItem, "load", _ensure_item_snapshot)

mapper_registry.map_imperatively(
    Inquiry,
    inquiries_table,
    properties={
        # Consent is the revision the visitor accepted; the fact of it is an
        # invariant of the aggregate and has no column of its own.
        "consent": composite(Consent, inquiries_table.c.consent_version),
        "_items": relationship(
            InquiryItem,
            cascade="all, delete-orphan",
            lazy="raise_on_sql",
            order_by=inquiry_items_table.c.id,
        ),
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
        "chosen": composite(
            ChosenValue,
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

mapper_registry.map_imperatively(
    Product,
    products_table,
    properties={
        "_price_from": products_table.c.price_from,
        "_declared_values": relationship(DeclaredValue, lazy="raise_on_sql"),
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
