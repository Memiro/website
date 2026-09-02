"""Read-only changelists over the mirrors: this slice only shows the domain.

Write screens arrive with their own tickets, each one routed through the same
interactor the API calls (ADR-0012); until then every screen here refuses
adding, changing and deleting.
"""

from typing import ClassVar, override

from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest

from memiro.presentation.django_admin.models import (
    Attribute,
    AttributeValue,
    Category,
    Inquiry,
    InquiryItem,
    PricingSettings,
    Product,
    ProductDeclaredValue,
    ProductImage,
    ProductVariant,
    SizeSurcharge,
)


class RefusesWrites:
    """Screen that shows the domain and accepts nothing back."""

    def has_change_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:  # noqa: ARG002  # Django's hook signature
        """Refuse: the domain is written through interactors, never through a mirror."""
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:  # noqa: ARG002  # Django's hook signature
        """Refuse: deletion rules belong to the database and the domain."""
        return False


class ReadOnlyAdmin(RefusesWrites, admin.ModelAdmin):
    """Changelist a mirror may show and no form anyone may submit."""

    @override
    def has_add_permission(self, request: HttpRequest) -> bool:
        """Refuse: the domain is written through interactors, never through a mirror."""
        return False


# Django's admin site refuses to register a model with a composite primary key,
# and three child tables of the domain have one; an inline knows no such
# restriction, and the card of the parent is where the owner edits them anyway.
class ReadOnlyInline(RefusesWrites, admin.TabularInline):
    """Child rows shown inside the card of the aggregate that owns them."""

    extra = 0
    can_delete = False
    show_change_link = False

    @override
    def has_add_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        """Refuse: the domain is written through interactors, never through a mirror."""
        return False


class ProductImageInline(ReadOnlyInline):
    """Фотографии товара."""

    model = ProductImage
    fields: ClassVar = ["key", "sort_order"]


class ProductDeclaredValueInline(ReadOnlyInline):
    """Объявленные значения товара."""

    model = ProductDeclaredValue
    fields: ClassVar = ["attribute", "value", "quantity"]


class SizeSurchargeInline(ReadOnlyInline):
    """Ступени наценки за размер."""

    model = SizeSurcharge
    fields: ClassVar = ["from_long_side_mm", "factor"]


@admin.register(Category)
class CategoryAdmin(ReadOnlyAdmin):
    """Разделы каталога."""

    list_display: ClassVar = ["name", "slug", "sort_order", "updated_at"]
    search_fields: ClassVar = ["name", "slug"]
    ordering: ClassVar = ["sort_order", "name"]


@admin.register(Attribute)
class AttributeAdmin(ReadOnlyAdmin):
    """Атрибуты разделов."""

    list_display: ClassVar = ["name", "category", "kind", "is_customer_changeable", "sort_order"]
    list_filter: ClassVar = ["kind", "is_customer_changeable", "category"]
    search_fields: ClassVar = ["name"]
    ordering: ClassVar = ["category", "sort_order", "name"]


@admin.register(AttributeValue)
class AttributeValueAdmin(ReadOnlyAdmin):
    """Справочник значений с тарифами."""

    list_display: ClassVar = [
        "name",
        "attribute",
        "rate_amount",
        "rate_unit",
        "scaled_by_shape",
        "scaled_by_size_surcharge",
        "marks_absence",
    ]
    list_filter: ClassVar = ["rate_unit", "scaled_by_shape", "scaled_by_size_surcharge", "marks_absence"]
    search_fields: ClassVar = ["name"]
    ordering: ClassVar = ["attribute", "sort_order", "name"]


@admin.register(Product)
class ProductAdmin(ReadOnlyAdmin):
    """Товары витрины."""

    list_display: ClassVar = ["name", "slug", "category", "is_published", "hides_calculated_price", "price_from"]
    list_filter: ClassVar = ["is_published", "hides_calculated_price", "category"]
    search_fields: ClassVar = ["name", "slug"]
    ordering: ClassVar = ["name"]
    inlines: ClassVar = [ProductDeclaredValueInline, ProductImageInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(ReadOnlyAdmin):
    """Предпосчитанные варианты."""

    list_display: ClassVar = ["product", "width_mm", "height_mm", "price", "sort_order"]
    list_filter: ClassVar = ["product"]
    ordering: ClassVar = ["product", "sort_order"]


@admin.register(PricingSettings)
class PricingSettingsAdmin(ReadOnlyAdmin):
    """Параметры расчёта."""

    list_display: ClassVar = [
        "min_area",
        "min_order_total",
        "max_long_side_mm",
        "max_short_side_mm",
        "updated_at",
    ]
    inlines: ClassVar = [SizeSurchargeInline]


@admin.register(Inquiry)
class InquiryAdmin(ReadOnlyAdmin):
    """Заявки посетителей."""

    list_display: ClassVar = ["name", "phone", "source", "created_at"]
    list_filter: ClassVar = ["source", "created_at"]
    search_fields: ClassVar = ["name", "phone", "email"]
    ordering: ClassVar = ["-created_at"]


@admin.register(InquiryItem)
class InquiryItemAdmin(ReadOnlyAdmin):
    """Строки заявок."""

    list_display: ClassVar = ["inquiry", "product_name", "verdict", "calculated_price", "price_from"]
    list_filter: ClassVar = ["verdict"]
    search_fields: ClassVar = ["product_name"]
