# django-stubs makes ModelAdmin, TabularInline and ModelForm generic, but
# Django does not implement __class_getitem__ on them: the parameter cannot be
# written without a runtime TypeError (the mypy side of this is in
# pyproject.toml). Unparameterized, every hook signature and every attribute
# django-stubs types through those parameters reads as Unknown to basedpyright.
# pyright: reportMissingTypeArgument=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownParameterType=false
# pyright: reportUnknownArgumentType=false
"""The owner's screens over the mirrors: the card of an attribute writes, the rest only read.

A write screen is routed through the same interactor the API calls, across the
bridge (ADR-0012); every screen that has not got its ticket yet refuses adding,
changing and deleting.
"""

from collections.abc import Iterable
from functools import partial
from typing import Any, override

from django.contrib import admin
from django.db.models import Model
from django.forms import BaseInlineFormSet, Form, ModelForm
from django.http import HttpRequest, HttpResponse

from memiro.application.common.input_limits import MAX_ATTRIBUTE_VALUES
from memiro.presentation.django_admin.attribute_card import create_attribute, remove_attribute, restate_attribute
from memiro.presentation.django_admin.forms import AttributeCardForm, AttributeValueRowForm
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
from memiro.presentation.django_admin.writes import guarded_write


def _submitted_rows(formsets: list[BaseInlineFormSet]) -> list[dict[str, Any]]:
    """Read the dictionary the owner left on the card, the rows he struck out excluded."""
    return [row for formset in formsets for row in formset.cleaned_data if row and not row.get("DELETE")]


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
    fields = (
        "key",
        "sort_order",
    )


class ProductDeclaredValueInline(ReadOnlyInline):
    """Объявленные значения товара."""

    model = ProductDeclaredValue
    fields = (
        "attribute",
        "value",
        "quantity",
    )


class SizeSurchargeInline(ReadOnlyInline):
    """Ступени наценки за размер."""

    model = SizeSurcharge
    fields = (
        "from_long_side_mm",
        "factor",
    )


@admin.register(Category)
class CategoryAdmin(ReadOnlyAdmin):
    """Разделы каталога."""

    list_display = (
        "name",
        "slug",
        "sort_order",
        "updated_at",
    )
    search_fields = (
        "name",
        "slug",
    )
    ordering = (
        "sort_order",
        "name",
    )


class AttributeValueInline(admin.TabularInline):
    """Значения справочника: карточка атрибута — единственное место, где их правят."""

    model = AttributeValue
    form = AttributeValueRowForm
    extra = 1
    max_num = MAX_ATTRIBUTE_VALUES
    ordering = (
        "sort_order",
        "name",
    )

    @override
    def get_formset(
        self,
        request: HttpRequest,
        obj: Model | None = None,
        **kwargs: Any,
    ) -> type[BaseInlineFormSet]:
        """Hold ``max_num`` as a rule, not as a hint: the application form refuses the same length."""
        return super().get_formset(request, obj, validate_max=True, **kwargs)


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    """Атрибуты разделов: карточка пишет домен командами агрегата."""

    form = AttributeCardForm
    inlines = (AttributeValueInline,)
    # No bulk action: the domain refuses a removal per aggregate, and a
    # queryset half deleted before the refusal is not something the owner
    # asked for. An attribute is removed from its own card.
    actions = None
    list_display = (
        "name",
        "category",
        "kind",
        "is_customer_changeable",
        "sort_order",
    )
    list_filter = (
        "kind",
        "is_customer_changeable",
        "category",
    )
    search_fields = ("name",)
    ordering = (
        "category",
        "sort_order",
        "name",
    )

    @override
    def get_readonly_fields(self, request: HttpRequest, obj: Model | None = None) -> tuple[str, ...]:
        """Keep a saved attribute in its section: ``ChangeAttributeData`` carries no category."""
        return () if obj is None else ("category",)

    @override
    def changeform_view(
        self,
        request: HttpRequest,
        object_id: str | None = None,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        """Send the card through the guard that owns refusals and the best-effort half (ADR-0012)."""
        view = partial(super().changeform_view, request, object_id, form_url, extra_context)
        return guarded_write(request, view)

    @override
    def delete_view(
        self,
        request: HttpRequest,
        object_id: str,
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        """Send the deletion through the same guard: a refusal names what still holds the attribute."""
        view = partial(super().delete_view, request, object_id, extra_context)
        return guarded_write(request, view)

    @override
    def save_model(self, request: HttpRequest, obj: Model, form: ModelForm, change: bool) -> None:
        """Write nothing here: the whole card is sent to the interactors by ``save_related``."""

    @override
    def save_related(
        self,
        request: HttpRequest,
        form: ModelForm,
        formsets: list[BaseInlineFormSet],
        change: bool,
    ) -> None:
        """Send the card — the root and the dictionary — as the commands of the aggregate."""
        rows = _submitted_rows(formsets)
        if change:
            restate_attribute(form.instance.pk, form.cleaned_data, rows)
            return
        # The mirror row is never inserted by Django, so the identifier the
        # command issued is what the history and the redirect are given.
        form.instance.pk = create_attribute(form.cleaned_data, rows)

    @override
    def construct_change_message(
        self,
        request: HttpRequest,
        form: Form,
        formsets: Iterable[Any] | None,
        add: bool = False,
    ) -> list[dict[str, dict[str, list[str]]]]:
        """Describe the change from the root alone: the dictionary is replaced whole, not row by row.

        Django reads what the formsets saved, and this card saves none of its
        own rows: the inline is sent to the aggregate instead.
        """
        return super().construct_change_message(request, form, (), add=add)

    @override
    def delete_model(self, request: HttpRequest, obj: Model) -> None:
        """Remove the attribute through the interactor that guards what still uses it."""
        remove_attribute(obj.pk)


@admin.register(AttributeValue)
class AttributeValueAdmin(ReadOnlyAdmin):
    """Справочник значений с тарифами."""

    list_display = (
        "name",
        "attribute",
        "rate_amount",
        "rate_unit",
        "scaled_by_shape",
        "scaled_by_size_surcharge",
        "marks_absence",
    )
    list_filter = (
        "rate_unit",
        "scaled_by_shape",
        "scaled_by_size_surcharge",
        "marks_absence",
    )
    search_fields = ("name",)
    ordering = (
        "attribute",
        "sort_order",
        "name",
    )


@admin.register(Product)
class ProductAdmin(ReadOnlyAdmin):
    """Товары витрины."""

    list_display = (
        "name",
        "slug",
        "category",
        "is_published",
        "hides_calculated_price",
        "price_from",
    )
    list_filter = (
        "is_published",
        "hides_calculated_price",
        "category",
    )
    search_fields = (
        "name",
        "slug",
    )
    ordering = ("name",)
    inlines = (
        ProductDeclaredValueInline,
        ProductImageInline,
    )


@admin.register(ProductVariant)
class ProductVariantAdmin(ReadOnlyAdmin):
    """Предпосчитанные варианты."""

    list_display = (
        "product",
        "width_mm",
        "height_mm",
        "price",
        "sort_order",
    )
    # No filter by product: the dropdown would carry one option per row of the
    # catalogue. Variants are read from the card of the product that owns them.
    search_fields = ("product__name",)
    ordering = (
        "product",
        "sort_order",
    )


@admin.register(PricingSettings)
class PricingSettingsAdmin(ReadOnlyAdmin):
    """Параметры расчёта."""

    list_display = (
        "min_area",
        "min_order_total",
        "max_long_side_mm",
        "max_short_side_mm",
        "updated_at",
    )
    inlines = (SizeSurchargeInline,)


@admin.register(Inquiry)
class InquiryAdmin(ReadOnlyAdmin):
    """Заявки посетителей."""

    list_display = (
        "name",
        "phone",
        "source",
        "created_at",
    )
    list_filter = (
        "source",
        "created_at",
    )
    search_fields = (
        "name",
        "phone",
        "email",
    )
    ordering = ("-created_at",)


@admin.register(InquiryItem)
class InquiryItemAdmin(ReadOnlyAdmin):
    """Строки заявок."""

    list_display = (
        "inquiry",
        "product_name",
        "verdict",
        "calculated_price",
        "price_from",
    )
    list_filter = ("verdict",)
    search_fields = ("product_name",)
