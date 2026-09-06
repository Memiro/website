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
from typing import Any, cast, override

from django.contrib import admin
from django.db.models import Model, QuerySet
from django.forms import BaseInlineFormSet, Form, ModelForm
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse

from memiro.application.common.input_limits import MAX_ATTRIBUTE_VALUES, MAX_SIZE_SURCHARGES
from memiro.entities.pricing.pricing_settings import PRICING_SETTINGS_ID
from memiro.presentation.django_admin.attribute_card import create_attribute, remove_attribute, restate_attribute
from memiro.presentation.django_admin.forms import (
    AttributeCardForm,
    AttributeValueRowForm,
    MaterialPriceRowForm,
    PricingSettingsForm,
    SizeSurchargeFormSet,
    SizeSurchargeTierForm,
)
from memiro.presentation.django_admin.materials_and_prices import restate_priced_row
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
from memiro.presentation.django_admin.pricing_settings_card import restate_pricing_settings
from memiro.presentation.django_admin.reprice import reprice_catalogue
from memiro.presentation.django_admin.writes import guarded_write


def _submitted_rows(formsets: list[BaseInlineFormSet]) -> list[dict[str, Any]]:
    """Read the dictionary the owner left on the card, the rows he struck out excluded."""
    return [row for formset in formsets for row in formset.cleaned_data if row and not row.get("DELETE")]


class GuardsItsForm:
    """Screen whose form is a write: every submit goes through the guard of ADR-0012."""

    def changeform_view(
        self,
        request: HttpRequest,
        object_id: str | None = None,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        """Send the form through the guard that owns refusals and the best-effort half (ADR-0012)."""
        view = partial(super().changeform_view, request, object_id, form_url, extra_context)  # type: ignore[misc]  # pyright: ignore[reportAttributeAccessIssue]  # the mixin is only ever mixed into a ``ModelAdmin``
        return guarded_write(request, view)


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
    # The mirror row is named for the flat price list; on this card the same
    # rows are the dictionary of one attribute.
    verbose_name = "значение"
    verbose_name_plural = "значения"
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
class AttributeAdmin(GuardsItsForm, admin.ModelAdmin):
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
class AttributeValueAdmin(GuardsItsForm, admin.ModelAdmin):
    """Материалы и цены: тарифы всех значений справочника поперёк атрибутов."""

    form = MaterialPriceRowForm
    # No bulk action and no row link: the flat list prices what already exists.
    # Naming, ordering, "means absence", adding and removing a row are the
    # card of the attribute, and this screen must not become a second one.
    actions = None
    list_display_links = None
    list_display = (
        "name",
        "attribute",
        "rate_unit",
        "rate_amount",
        "scaled_by_shape",
        "scaled_by_size_surcharge",
        "marks_absence",
    )
    list_editable = (
        "rate_unit",
        "rate_amount",
        "scaled_by_shape",
        "scaled_by_size_surcharge",
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

    @override
    def has_add_permission(self, request: HttpRequest) -> bool:
        """Refuse: a dictionary row is born on the card of the attribute that owns it."""
        return False

    @override
    def has_delete_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:  # Django's hook signature
        """Refuse: a row leaves the dictionary by the command of its attribute, not from here."""
        return False

    @override
    def changelist_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        """Send the edited rows through the guard that owns refusals and the best-effort half."""
        view = partial(super().changelist_view, request, extra_context)
        return guarded_write(request, view)

    @override
    def save_model(self, request: HttpRequest, obj: Model, form: ModelForm, change: bool) -> None:
        """Send the priced row to the command of its attribute; the mirror itself is never written."""
        restate_priced_row(cast("AttributeValue", obj))


@admin.register(Product)
class ProductAdmin(ReadOnlyAdmin):
    """Товары витрины: карточка только читает, а пересчёт цен зовёт хендлер событий."""

    actions = ("reprice_products",)
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

    @override
    def changelist_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        """Send the action through the guard that owns refusals and the banner of the reprice."""
        view = partial(super().changelist_view, request, extra_context)
        return guarded_write(request, view)

    @admin.action(description="Пересчитать цены")
    def reprice_products(self, request: HttpRequest, queryset: QuerySet[Model]) -> None:  # noqa: ARG002  # Django's action signature
        """Reprice the catalogue by the same handler the domain events run."""
        # The selection is not narrowed: prices are one table, a tariff moves
        # every variant that uses it, and repricing a chosen half of the
        # catalogue would leave the other half showing yesterday's numbers
        # (ADR-0014).
        reprice_catalogue()


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


class SizeSurchargeInline(admin.TabularInline):
    """Ступени наценки за размер: набор заменяется целиком одной командой корня."""

    model = SizeSurcharge
    form = SizeSurchargeTierForm
    formset = SizeSurchargeFormSet
    max_num = MAX_SIZE_SURCHARGES
    can_delete = True
    show_change_link = False
    ordering = ("from_long_side_mm",)

    @override
    def get_formset(
        self,
        request: HttpRequest,
        obj: Model | None = None,
        **kwargs: Any,
    ) -> type[BaseInlineFormSet]:
        """Hold ``max_num`` as a rule, not as a hint: the application form refuses the same length."""
        return super().get_formset(request, obj, validate_max=True, **kwargs)


@admin.register(PricingSettings)
class PricingSettingsAdmin(GuardsItsForm, admin.ModelAdmin):
    """Параметры расчёта: границы и ступени наценки одной командой."""

    form = PricingSettingsForm
    inlines = (SizeSurchargeInline,)
    actions = None

    @override
    def has_add_permission(self, request: HttpRequest) -> bool:
        """Refuse: the site has exactly one row of settings, born with it."""
        return False

    @override
    def has_delete_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:  # Django's hook signature
        """Refuse: without the settings row the catalogue has no price at all."""
        return False

    @override
    def changelist_view(
        self, request: HttpRequest, extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:  # Django's hook signature
        """Send the owner to the only object there is: a list of one row is not a screen."""
        return HttpResponseRedirect(reverse("admin:memiro_pricingsettings_change", args=[PRICING_SETTINGS_ID]))

    @override
    def save_model(self, request: HttpRequest, obj: Model, form: ModelForm, change: bool) -> None:
        """Write nothing here: the whole screen is sent to the interactor by ``save_related``."""

    @override
    def save_related(
        self,
        request: HttpRequest,
        form: ModelForm,
        formsets: list[BaseInlineFormSet],
        change: bool,
    ) -> None:
        """Send the bounds and the surcharge table as the one command of the aggregate."""
        restate_pricing_settings(form.cleaned_data, _submitted_rows(formsets))

    @override
    def construct_change_message(
        self,
        request: HttpRequest,
        form: Form,
        formsets: Iterable[Any] | None,
        add: bool = False,
    ) -> list[dict[str, dict[str, list[str]]]]:
        """Describe the change from the bounds alone: the tiers are replaced whole, not row by row."""
        return super().construct_change_message(request, form, (), add=add)


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
