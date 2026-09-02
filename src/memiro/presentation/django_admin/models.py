"""Mirrors of the domain tables: Django reads them, alembic owns them (ADR-0012).

``managed = False`` and an explicit ``db_table`` everywhere, ``DO_NOTHING`` on
every foreign key — deletion rules belong to the database and to the domain.
``test_admin_mirror_matches_schema`` is what keeps these declarations honest.
"""

from enum import StrEnum
from typing import ClassVar, override

from django.contrib.postgres.fields import ArrayField
from django.db import models

from memiro.entities.catalog.attribute.entity import AttributeKind
from memiro.entities.catalog.attribute.rate import Unit
from memiro.entities.inquiry.entity import InquirySource
from memiro.entities.pricing.quotation import PricingVerdict

NAME_LENGTH = 255


def _choices(enum: type[StrEnum]) -> list[tuple[str, str]]:
    """List the stored member names of a domain enum for a mirror column."""
    return [(member.name, member.name) for member in enum]


class Mirror(models.Model):
    """Base of every read mirror: unmanaged, never migrated by Django."""

    class Meta:
        abstract = True
        managed = False


class Category(Mirror):
    """Раздел каталога."""

    id = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=NAME_LENGTH)
    slug = models.CharField(max_length=NAME_LENGTH, unique=True)
    sort_order = models.IntegerField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta(Mirror.Meta):
        db_table = "categories"
        verbose_name = "раздел"
        verbose_name_plural = "разделы"

    @override
    def __str__(self) -> str:
        return str(self.name)


class Attribute(Mirror):
    """Свойство товара, которое покупатель выбирает или задаёт числом."""

    id = models.UUIDField(primary_key=True)
    # The column carries no database foreign key; the mirror navigates it
    # without claiming one (``db_constraint=False``).
    category = models.ForeignKey(
        Category,
        on_delete=models.DO_NOTHING,
        db_column="category_id",
        db_constraint=False,
        related_name="attributes",
    )
    name = models.CharField(max_length=NAME_LENGTH)
    kind = models.CharField(max_length=NAME_LENGTH, choices=_choices(AttributeKind))
    parent_ids = ArrayField(models.UUIDField())
    is_customer_changeable = models.BooleanField()
    sort_order = models.IntegerField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta(Mirror.Meta):
        db_table = "attributes"
        verbose_name = "атрибут"
        verbose_name_plural = "атрибуты"

    @override
    def __str__(self) -> str:
        return str(self.name)


class AttributeValue(Mirror):
    """Значение справочника со своим тарифом."""

    id = models.UUIDField(primary_key=True)
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.DO_NOTHING,
        db_column="attribute_id",
        related_name="values",
    )
    name = models.CharField(max_length=NAME_LENGTH)
    rate_amount = models.DecimalField(max_digits=12, decimal_places=4)
    rate_unit = models.CharField(max_length=NAME_LENGTH, choices=_choices(Unit))
    scaled_by_shape = models.BooleanField()
    scaled_by_size_surcharge = models.BooleanField()
    marks_absence = models.BooleanField()
    sort_order = models.IntegerField()

    class Meta(Mirror.Meta):
        db_table = "attribute_values"
        verbose_name = "значение"
        verbose_name_plural = "значения"

    @override
    def __str__(self) -> str:
        return str(self.name)


class Product(Mirror):
    """Товар витрины."""

    id = models.UUIDField(primary_key=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.DO_NOTHING,
        db_column="category_id",
        db_constraint=False,
        related_name="products",
    )
    name = models.CharField(max_length=NAME_LENGTH)
    slug = models.CharField(max_length=NAME_LENGTH, unique=True)
    description = models.CharField(max_length=2_000)
    is_published = models.BooleanField()
    hides_calculated_price = models.BooleanField()
    price_from = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta(Mirror.Meta):
        db_table = "products"
        verbose_name = "товар"
        verbose_name_plural = "товары"

    @override
    def __str__(self) -> str:
        return str(self.name)


class ProductImage(Mirror):
    """Фотография товара в его галерее."""

    pk = models.CompositePrimaryKey("product_id", "key")
    product = models.ForeignKey(
        Product,
        on_delete=models.DO_NOTHING,
        db_column="product_id",
        related_name="images",
    )
    key = models.CharField(max_length=NAME_LENGTH)
    sort_order = models.IntegerField()

    class Meta(Mirror.Meta):
        db_table = "product_images"
        verbose_name = "фотография"
        verbose_name_plural = "фотографии"

    @override
    def __str__(self) -> str:
        return str(self.key)


class ProductDeclaredValue(Mirror):
    """Объявленное владельцем значение атрибута у товара."""

    pk = models.CompositePrimaryKey("product_id", "attribute_id")
    product = models.ForeignKey(
        Product,
        on_delete=models.DO_NOTHING,
        db_column="product_id",
        related_name="declared_values",
    )
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.DO_NOTHING,
        db_column="attribute_id",
        related_name="declarations",
    )
    value = models.ForeignKey(
        AttributeValue,
        on_delete=models.DO_NOTHING,
        db_column="value_id",
        related_name="declarations",
        null=True,
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=4, null=True)

    class Meta(Mirror.Meta):
        db_table = "product_declared_values"
        verbose_name = "объявленное значение"
        verbose_name_plural = "объявленные значения"

    @override
    def __str__(self) -> str:
        return str(self.pk)


class ProductVariant(Mirror):
    """Предпосчитанный вариант товара с ценой."""

    id = models.UUIDField(primary_key=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.DO_NOTHING,
        db_column="product_id",
        related_name="variants",
    )
    width_mm = models.IntegerField()
    height_mm = models.IntegerField()
    overrides = models.JSONField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    sort_order = models.IntegerField()
    fingerprint = models.UUIDField()

    class Meta(Mirror.Meta):
        db_table = "product_variants"
        verbose_name = "вариант"
        verbose_name_plural = "варианты"
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["product", "fingerprint"],
                name="uq_product_variants_product_fingerprint",
            ),
        ]

    @override
    def __str__(self) -> str:
        return f"{self.width_mm}×{self.height_mm}"


class PricingSettings(Mirror):
    """Параметры расчёта: предел производства и минимальный заказ."""

    id = models.UUIDField(primary_key=True)
    min_area = models.DecimalField(max_digits=10, decimal_places=4)
    min_order_total = models.DecimalField(max_digits=12, decimal_places=2)
    max_long_side_mm = models.IntegerField()
    max_short_side_mm = models.IntegerField()
    updated_at = models.DateTimeField()

    class Meta(Mirror.Meta):
        db_table = "pricing_settings"
        verbose_name = "параметры расчёта"
        verbose_name_plural = "параметры расчёта"

    @override
    def __str__(self) -> str:
        return "параметры расчёта"


class SizeSurcharge(Mirror):
    """Ступень наценки за размер (ADR-0010)."""

    # The column is ``numeric`` without a declared precision; the mirror reads
    # it at the width the rest of the pricing columns use.
    pk = models.CompositePrimaryKey("pricing_settings_id", "from_long_side_mm")
    pricing_settings = models.ForeignKey(
        PricingSettings,
        on_delete=models.DO_NOTHING,
        db_column="pricing_settings_id",
        related_name="size_surcharges",
    )
    from_long_side_mm = models.IntegerField()
    factor = models.DecimalField(max_digits=12, decimal_places=4)

    class Meta(Mirror.Meta):
        db_table = "size_surcharges"
        verbose_name = "ступень наценки"
        verbose_name_plural = "ступени наценки"

    @override
    def __str__(self) -> str:
        return f"от {self.from_long_side_mm} мм"


class Inquiry(Mirror):
    """Заявка посетителя."""

    id = models.UUIDField(primary_key=True)
    source = models.CharField(max_length=NAME_LENGTH, choices=_choices(InquirySource))
    name = models.CharField(max_length=NAME_LENGTH)
    phone = models.CharField(max_length=NAME_LENGTH)
    # The column really is nullable; a mirror that says otherwise is drift.
    email = models.CharField(max_length=NAME_LENGTH, null=True)  # noqa: DJ001
    comment = models.CharField(max_length=2_000)
    consent_version = models.CharField(max_length=NAME_LENGTH)
    created_at = models.DateTimeField()

    class Meta(Mirror.Meta):
        db_table = "inquiries"
        verbose_name = "заявка"
        verbose_name_plural = "заявки"

    @override
    def __str__(self) -> str:
        return str(self.name)


class InquiryItem(Mirror):
    """Строка заявки со снимком расчёта."""

    id = models.UUIDField(primary_key=True)
    inquiry = models.ForeignKey(
        Inquiry,
        on_delete=models.DO_NOTHING,
        db_column="inquiry_id",
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.DO_NOTHING,
        db_column="product_id",
        related_name="inquiry_items",
    )
    product_name = models.CharField(max_length=NAME_LENGTH)
    price_from = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    configuration = models.JSONField(null=True)
    calculated_price = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    verdict = models.CharField(max_length=NAME_LENGTH, choices=_choices(PricingVerdict))
    wish = models.CharField(max_length=1_000)

    class Meta(Mirror.Meta):
        db_table = "inquiry_items"
        verbose_name = "строка заявки"
        verbose_name_plural = "строки заявок"

    @override
    def __str__(self) -> str:
        return str(self.product_name)
