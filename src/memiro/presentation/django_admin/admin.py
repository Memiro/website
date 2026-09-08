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

from collections.abc import Callable, Iterable
from contextvars import ContextVar
from functools import partial
from typing import Any, cast, override
from uuid import UUID

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.options import Action, ActionLocation
from django.contrib.admin.views.main import ChangeList
from django.db.models import Model, QuerySet
from django.forms import BaseInlineFormSet, Form, ModelForm
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import URLPattern, path, reverse
from django.utils.html import format_html

from memiro.application.common.input_limits import MAX_ATTRIBUTE_VALUES, MAX_SIZE_SURCHARGES
from memiro.application.manage_products import PricingGapsModel
from memiro.entities.common.identifiers import ProductId
from memiro.entities.pricing.pricing_settings import PRICING_SETTINGS_ID
from memiro.presentation.django_admin.attribute_card import create_attribute, remove_attribute, restate_attribute
from memiro.presentation.django_admin.forms import (
    AttributeCardForm,
    AttributeValueRowForm,
    CategoryCardForm,
    LandingCardForm,
    MaterialPriceRowForm,
    PricingSettingsForm,
    ProductCardForm,
    SizeSurchargeFormSet,
    SizeSurchargeTierForm,
    WorkCardForm,
    declared_value_fields,
    photo_fields,
)
from memiro.presentation.django_admin.landing_card import create_landing, remove_landing, restate_landing
from memiro.presentation.django_admin.materials_and_prices import restate_priced_row
from memiro.presentation.django_admin.models import (
    Attribute,
    AttributeValue,
    Category,
    Inquiry,
    InquiryItem,
    Landing,
    LandingCondition,
    PricingSettings,
    Product,
    ProductImage,
    ProductVariant,
    SellerRequisites,
    SiteContacts,
    SizeSurcharge,
    Work,
)
from memiro.presentation.django_admin.pricing_settings_card import restate_pricing_settings
from memiro.presentation.django_admin.product_card import (
    create_product,
    pricing_gaps_of,
    remove_product,
    restate_gallery,
    restate_product,
)
from memiro.presentation.django_admin.reprice import reprice_catalogue
from memiro.presentation.django_admin.section_card import stamped_now
from memiro.presentation.django_admin.variant_builder import (
    answered,
    builder_context,
    forbidden,
    quoted,
    removed,
    saved,
)
from memiro.presentation.django_admin.work_card import create_work, remove_work, restate_work
from memiro.presentation.django_admin.writes import guarded_write

# What the list says about a product whose calculator is not ready: the
# machine answer comes from the domain, the sentence is the admin's (§12.4).
NOTHING_TO_SAY = "—"
UNDECLARED = "Не заполнено:"
NOTHING_IS_PAID = "Ни одно значение не стоит денег."

# The three addresses of the panel, under the card of the product they belong
# to: a variant of nobody's product does not exist.
VARIANT_PRICE_URL = "memiro_product_variant_price"
VARIANT_SAVE_URL = "memiro_product_variant_save"
VARIANT_DELETE_URL = "memiro_product_variant_delete"

# One answer of the panel, as the URL conf hands it a request.
type PanelView = Callable[[HttpRequest, ProductId], HttpResponse]

# What one rendering of the product list learned about its own rows: asked
# once by the list, read by every row of it, and dropped with the request.
_NO_GAPS: dict[ProductId, PricingGapsModel] = {}
_page_gaps: ContextVar[dict[ProductId, PricingGapsModel]] = ContextVar("memiro_admin_pricing_gaps", default=_NO_GAPS)


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
    """Фотографии товара: заводят и убирают их полями карточки, здесь их видно."""

    model = ProductImage
    fields = (
        "preview",
        "key",
        "sort_order",
    )
    readonly_fields = ("preview",)

    @admin.display(description="Фотография")
    def preview(self, obj: Model) -> str:
        """Show the photo the way the storefront gets it: from the edge, by its key."""
        key = cast("ProductImage", obj).key
        return format_html('<img src="{}{}" alt="{}" style="max-height: 6rem">', settings.MEDIA_URL, key, key)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Разделы каталога: содержимое без правил, поэтому его правят напрямую (решение 3)."""

    form = CategoryCardForm
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

    @override
    def save_model(self, request: HttpRequest, obj: Model, form: ModelForm, change: bool) -> None:
        """Stamp the row before writing it: time is taken from the clock, never invented by the ORM (§1.7)."""
        section = cast("Category", obj)
        stamped = stamped_now()
        if not change:
            section.created_at = stamped
        section.updated_at = stamped
        super().save_model(request, obj, form, change)


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


def _panel(product_id: ProductId) -> dict[str, Any]:
    """Build the panel of one saved product, its three addresses resolved by the URL conf."""
    return builder_context(product_id) | {
        "price_url": reverse(f"admin:{VARIANT_PRICE_URL}", args=[product_id]),
        "save_url": reverse(f"admin:{VARIANT_SAVE_URL}", args=[product_id]),
        "delete_url": reverse(f"admin:{VARIANT_DELETE_URL}", args=[product_id]),
    }


class ProductChangeList(ChangeList):
    """Список товаров, который спрашивает домен обо всей своей странице разом."""

    @override
    def get_results(self, request: HttpRequest) -> None:
        """Ask about the page in one question: a row at a time would be a query per row."""
        super().get_results(request)
        _page_gaps.set(pricing_gaps_of([cast("Product", product).id for product in self.result_list]))


def _card_form(obj: Model | None) -> type[ModelForm]:
    """Build the card of one product: a field per attribute of its section, and the gallery it already has."""
    if obj is None:
        return ProductCardForm
    product = cast("Product", obj)
    section: UUID = product.category_id  # pyright: ignore[reportAttributeAccessIssue]  # the raw column behind a mirror foreign key
    return type(ProductCardForm.__name__, (ProductCardForm,), declared_value_fields(section) | photo_fields(product.id))


@admin.register(Product)
class ProductAdmin(GuardsItsForm, admin.ModelAdmin):
    """Товары витрины: карточка пишет домен командами агрегата, а пересчёт цен зовёт хендлер событий."""

    form = ProductCardForm
    inlines = (ProductImageInline,)
    actions = ("reprice_products",)
    change_form_template = "admin/memiro/product/change_form.html"

    class Media:
        """Django prints the panel's script and styles into the head of the card."""

        css = {"all": ("memiro/css/admin-variants.css",)}  # noqa: RUF012  # Django reads Media options off the class as plain values
        js = ("memiro/js/admin-variant-builder.js",)

    list_display = (
        "name",
        "slug",
        "category",
        "is_published",
        "hides_calculated_price",
        "price_from",
        "missing_for_the_calculator",
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

    @override
    def get_actions(
        self,
        request: HttpRequest,
        action_location: ActionLocation = ActionLocation.CHANGE_LIST,
    ) -> dict[str, Action | None]:
        """Leave the bulk deletion off the list: a product is removed from its own card, one refusal at a time."""
        actions = super().get_actions(request, action_location)
        actions.pop("delete_selected", None)
        return actions

    @override
    def get_changelist(self, request: HttpRequest, **kwargs: Any) -> type[ChangeList]:
        """Use the list that asks the domain what its rows are still missing."""
        return ProductChangeList

    @override
    def get_form(
        self,
        request: HttpRequest,
        obj: Model | None = None,
        change: bool = False,
        **kwargs: Any,
    ) -> type[ModelForm]:
        """Give a saved product a field per attribute of its section: a new one has no section yet."""
        kwargs["form"] = _card_form(obj)
        return super().get_form(request, obj, change=change, **kwargs)

    @override
    def get_urls(self) -> list[URLPattern]:
        """Hang the three answers of the panel under the card of the product they belong to."""
        own = [
            path(
                "<uuid:product_id>/variants/price/",
                self.admin_site.admin_view(self._permitted(self.variant_price)),
                name=VARIANT_PRICE_URL,
            ),
            path(
                "<uuid:product_id>/variants/save/",
                self.admin_site.admin_view(self._permitted(self.variant_save)),
                name=VARIANT_SAVE_URL,
            ),
            path(
                "<uuid:product_id>/variants/delete/",
                self.admin_site.admin_view(self._permitted(self.variant_delete)),
                name=VARIANT_DELETE_URL,
            ),
        ]
        return own + super().get_urls()

    @override
    def render_change_form(
        self,
        request: HttpRequest,
        context: dict[str, Any],
        add: bool = False,
        change: bool = False,
        form_url: str = "",
        obj: Model | None = None,
    ) -> HttpResponse:
        """Give the card of a saved product its panel: an unsaved one has nothing to build variants of."""
        context["variant_builder"] = None if obj is None else _panel(cast("Product", obj).id)
        return super().render_change_form(request, context, add=add, change=change, form_url=form_url, obj=obj)

    def _permitted(self, view: PanelView) -> PanelView:
        """Keep the panel behind the permission of the card: ``admin_view`` asks about the door, not the product."""

        def permitted(request: HttpRequest, product_id: ProductId) -> HttpResponse:
            if not self.has_change_permission(request):
                return forbidden()
            return view(request, product_id)

        return permitted

    def variant_price(self, request: HttpRequest, product_id: ProductId) -> HttpResponse:
        """Answer what the assembled variant would cost, by the function that would save it."""
        return answered(request, lambda: quoted(request, product_id))

    def variant_save(self, request: HttpRequest, product_id: ProductId) -> HttpResponse:
        """Write the assembled variant and answer with the whole redrawn panel."""
        return answered(request, lambda: saved(request, product_id))

    def variant_delete(self, request: HttpRequest, product_id: ProductId) -> HttpResponse:
        """Take one variant off the product and answer with the whole redrawn panel."""
        return answered(request, lambda: removed(request, product_id))

    @override
    def changelist_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        """Send the action through the guard that owns refusals and the banner of the reprice."""
        view = partial(super().changelist_view, request, extra_context)
        # Cleared before the list is built, never after: the changelist is a
        # ``TemplateResponse``, and its rows are rendered once this view has
        # already returned. What a previous page learned cannot leak into a
        # rendering whose own ``get_results`` never ran.
        _page_gaps.set(_NO_GAPS)
        return guarded_write(request, view)

    @override
    def delete_view(
        self,
        request: HttpRequest,
        object_id: str,
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        """Send the deletion through the same guard: what the command refuses comes back as a message."""
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
        """Send the card — the root, the declared set and the gallery — as the commands of the aggregate."""
        if change:
            restate_product(form.instance.pk, form.cleaned_data)
            restate_gallery(form.instance.pk, form.cleaned_data)
            return
        # The mirror row is never inserted by Django, so the identifier the
        # command issued is what the history and the redirect are given.
        form.instance.pk = create_product(form.cleaned_data)

    @override
    def delete_model(self, request: HttpRequest, obj: Model) -> None:
        """Remove the product through the interactor that owns everything belonging to it."""
        remove_product(obj.pk)

    @admin.display(description="Чего не хватает для калькулятора")
    def missing_for_the_calculator(self, obj: Model) -> str:
        """Say why the product shows no calculated price, in the owner's words (``product.md``, правило 10)."""
        gaps = _page_gaps.get().get(cast("Product", obj).id)
        if gaps is None:
            return NOTHING_TO_SAY
        if gaps.undeclared_attributes:
            return f"{UNDECLARED} {', '.join(gaps.undeclared_attributes)}."
        return NOTHING_IS_PAID if gaps.nothing_is_paid else NOTHING_TO_SAY

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


class LandingConditionInline(ReadOnlyInline):
    """Сужение как оно сохранено: правят его полем «Сужение» на карточке."""

    model = LandingCondition
    verbose_name = "условие"
    verbose_name_plural = "сужение страницы"
    fields = (
        "attribute",
        "value",
    )


@admin.register(Landing)
class LandingAdmin(GuardsItsForm, admin.ModelAdmin):
    """Посадочные страницы: карточка пишет домен командами агрегата."""

    form = LandingCardForm
    inlines = (LandingConditionInline,)
    # No bulk action: a page is removed from its own card, and a queryset half
    # deleted before a refusal is not something the owner asked for.
    actions = None
    list_display = (
        "heading",
        "slug",
        "category",
        "is_published",
        "sort_order",
    )
    list_filter = (
        "category",
        "is_published",
    )
    search_fields = (
        "heading",
        "slug",
    )
    ordering = (
        "sort_order",
        "heading",
    )

    @override
    def get_readonly_fields(self, request: HttpRequest, obj: Model | None = None) -> tuple[str, ...]:
        """Keep a saved page on its category: a move would leave it without one condition of its own."""
        return () if obj is None else ("category",)

    @override
    def delete_view(
        self,
        request: HttpRequest,
        object_id: str,
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        """Send the deletion through the same guard the form goes through."""
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
        """Send the card — the copy and the narrowing — as the command of the aggregate."""
        if change:
            restate_landing(form.instance.pk, form.cleaned_data)
            return
        # The mirror row is never inserted by Django, so the identifier the
        # command issued is what the history and the redirect are given.
        form.instance.pk = create_landing(form.cleaned_data)

    @override
    def construct_change_message(
        self,
        request: HttpRequest,
        form: Form,
        formsets: Iterable[Any] | None,
        add: bool = False,
    ) -> list[dict[str, dict[str, list[str]]]]:
        """Describe the change from the card alone: the narrowing is replaced whole, not row by row."""
        return super().construct_change_message(request, form, (), add=add)

    @override
    def delete_model(self, request: HttpRequest, obj: Model) -> None:
        """Remove the page through the interactor that takes its narrowing with it."""
        remove_landing(obj.pk)


@admin.register(Work)
class WorkAdmin(GuardsItsForm, admin.ModelAdmin):
    """Наши работы: карточка пишет галерею командами, фотография уходит на том через порт."""

    form = WorkCardForm
    # No bulk action: a work is removed from its own card, and a queryset half
    # deleted before a refusal is not something the owner asked for.
    actions = None
    list_display = (
        "preview",
        "title",
        "product",
        "is_published",
        "sort_order",
    )
    list_filter = ("is_published",)
    search_fields = ("title",)
    ordering = (
        "sort_order",
        "title",
    )

    @admin.display(description="Фотография")
    def preview(self, obj: Model) -> str:
        """Show the photo the way the storefront gets it: from the edge, by its key."""
        work = cast("Work", obj)
        return format_html(
            '<img src="{}{}" alt="{}" style="max-height: 6rem">', settings.MEDIA_URL, work.photo_key, work.title
        )

    @override
    def delete_view(
        self,
        request: HttpRequest,
        object_id: str,
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        """Send the deletion through the same guard the form goes through."""
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
        """Send the card as the command of the gallery: the photograph goes with it."""
        if change:
            restate_work(form.instance.pk, form.cleaned_data)
            return
        # The mirror row is never inserted by Django, so the identifier the
        # command issued is what the history and the redirect are given.
        form.instance.pk = create_work(form.cleaned_data)

    @override
    def delete_model(self, request: HttpRequest, obj: Model) -> None:
        """Remove the work through the interactor that takes its photograph with it."""
        remove_work(obj.pk)


@admin.register(SiteContacts)
class SiteContactsAdmin(ReadOnlyAdmin):
    """The studio contacts the storefront prints."""

    list_display = (
        "phone_display",
        "email",
        "city",
        "updated_at",
    )


@admin.register(SellerRequisites)
class SellerRequisitesAdmin(ReadOnlyAdmin):
    """The seller requisites printed in the storefront footer."""

    list_display = (
        "name",
        "ogrn",
        "inn",
        "updated_at",
    )
