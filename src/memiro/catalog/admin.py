from typing import TYPE_CHECKING, Any, ClassVar

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, ModelForm
from django.utils.html import format_html

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.db.models.fields.files import ImageFieldFile
    from django.http import HttpRequest

from .models import (
    MAX_LANDING_CONDITIONS,
    Attribute,
    AttributeValue,
    Category,
    Landing,
    LandingCondition,
    PricingSettings,
    Product,
    ProductAttribute,
    ProductImage,
)


def _preview(image: ImageFieldFile) -> str:
    if not image:
        return "—"
    return format_html(
        '<img src="{}" style="max-height: 80px;" alt="">',
        image.url,
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order")
    list_editable = ("order",)
    prepopulated_fields: ClassVar = {"slug": ("name",)}


class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 1


# Одно правило — одна формулировка: атрибут чужой категории отвергают
# и товар, и родитель, и владелец читает об этом одно и то же
FOREIGN_CATEGORY = "«%(name)s» — атрибут другой категории."


class AttributeForm(ModelForm):
    """Форма атрибута: родители — только свои по категории.

    `parents` — связь многие-ко-многим, до сохранения модели её не
    видно, поэтому проверка живёт здесь, а не в `Model.clean`.
    """

    def clean_parents(self) -> QuerySet[Attribute]:
        parents: QuerySet[Attribute] = self.cleaned_data["parents"]
        category = self.cleaned_data.get("category")
        for parent in parents:
            if parent.pk == self.instance.pk:
                message = "Атрибут не зависит сам от себя."
                raise ValidationError(message)
            if category and not parent.belongs_to(category.pk):
                raise ValidationError(
                    FOREIGN_CATEGORY, params={"name": parent.name}
                )
            # В кольце зависимостей не сохранить ни одного из атрибутов:
            # каждому вечно не хватает другого
            if self.instance.pk and parent.depends_on(self.instance):
                message = "«%(name)s» уже опирается на этот атрибут."
                raise ValidationError(message, params={"name": parent.name})
        return parents


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    form = AttributeForm
    list_display = (
        "name",
        "category",
        "kind",
        "is_customer_editable",
        "order",
    )
    list_filter = ("category", "kind", "is_customer_editable")
    list_editable = ("order",)
    prepopulated_fields: ClassVar = {"slug": ("name",)}
    filter_horizontal = ("parents",)
    inlines = (AttributeValueInline,)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    readonly_fields = ("preview",)

    @admin.display(description="превью")
    def preview(self, obj: ProductImage) -> str:
        return _preview(obj.image)


def _kept_rows(formset: BaseInlineFormSet) -> list[dict[str, Any]]:
    """Строки инлайна, которые останутся после сохранения.

    Помеченные на удаление не проверяем: смена категории вместе с
    удалением старых строк — один шаг.
    """
    return [
        form.cleaned_data
        for form in formset.forms
        if form.cleaned_data and not form.cleaned_data.get("DELETE")
    ]


def _attributes(rows: list[dict[str, Any]]) -> list[Attribute]:
    """Атрибуты оставшихся строк инлайна; незаполненные пропускаем."""
    return [row["attribute"] for row in rows if row.get("attribute")]


def _check_own_category(
    attributes: list[Attribute], category_id: int | None
) -> None:
    """Атрибуты чужой категории в инлайне — ошибка.

    Пока родитель не сохранён, model.clean его категории не видит,
    поэтому проверка живёт в формсете.
    """
    if not category_id:
        return
    for attribute in attributes:
        if not attribute.belongs_to(category_id):
            raise ValidationError(
                FOREIGN_CATEGORY, params={"name": attribute.name}
            )


def _present_attribute_ids(rows: list[dict[str, Any]]) -> set[int]:
    """Атрибуты, признак которых у товара есть.

    «Да/нет» со значением «нет» — это отсутствие признака, а не его
    наличие: кнопки не бывает при «подогрев: нет» ровно так же, как
    при незаведённом подогреве (CONTEXT.md, тикет 22).
    """
    return {
        row["attribute"].pk
        for row in rows
        if row.get("attribute") and row.get("value_bool") is not False
    }


def _check_parents(rows: list[dict[str, Any]]) -> None:
    """Значение атрибута-ребёнка без родителя — ошибка с объяснением.

    Формсет знает весь набор атрибутов товара, поэтому родителя и
    ребёнка владелец заводит одним сохранением.
    """
    present = _present_attribute_ids(rows)
    for attribute in _attributes(rows):
        message = attribute.missing_parent_error(present)
        if message:
            raise ValidationError(message)


class ProductAttributeFormSet(BaseInlineFormSet):
    def clean(self) -> None:
        super().clean()
        rows = _kept_rows(self)
        _check_own_category(_attributes(rows), self.instance.category_id)
        _check_parents(rows)


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    formset = ProductAttributeFormSet
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "price",
        "is_published",
        "is_popular",
        "is_promo",
        "order",
    )
    list_filter = ("category", "is_published", "is_popular", "is_promo")
    list_editable = ("is_published", "is_popular", "is_promo", "order")
    search_fields = ("name", "article")
    prepopulated_fields: ClassVar = {"slug": ("name",)}
    readonly_fields = ("preview_small", "preview_large")
    inlines = (ProductImageInline, ProductAttributeInline)

    @admin.display(description="превью малого фото")
    def preview_small(self, obj: Product) -> str:
        return _preview(obj.photo_small)

    @admin.display(description="превью большого фото")
    def preview_large(self, obj: Product) -> str:
        return _preview(obj.photo_large)


@admin.register(PricingSettings)
class PricingSettingsAdmin(admin.ModelAdmin):
    """Пороги расчёта: одна строка на сайт, её правят, а не заводят."""

    list_display = ("min_area_m2", "min_order_total")

    def has_add_permission(
        self,
        request: HttpRequest,  # noqa: ARG002
    ) -> bool:
        return not PricingSettings.objects.exists()

    def has_delete_permission(
        self,
        request: HttpRequest,  # noqa: ARG002
        obj: PricingSettings | None = None,  # noqa: ARG002
    ) -> bool:
        return False


class LandingConditionFormSet(BaseInlineFormSet):
    def clean(self) -> None:
        """Посадочная — категория и одно-два условия (ADR-0003).

        Без условий это дубль категории, с длинным хвостом — мусор
        в индексе.
        """
        super().clean()
        kept = _kept_rows(self)
        if not kept:
            message = "Добавьте хотя бы одно условие."
            raise ValidationError(message)
        if len(kept) > MAX_LANDING_CONDITIONS:
            message = "Условий не больше %(limit)s."
            raise ValidationError(
                message, params={"limit": MAX_LANDING_CONDITIONS}
            )
        _check_own_category(_attributes(kept), self.instance.category_id)


class LandingConditionInline(admin.TabularInline):
    model = LandingCondition
    formset = LandingConditionFormSet
    extra = 1


@admin.register(Landing)
class LandingAdmin(admin.ModelAdmin):
    list_display = ("heading", "slug", "category", "is_published", "order")
    list_filter = ("category", "is_published")
    list_editable = ("is_published", "order")
    search_fields = ("heading", "title", "slug")
    prepopulated_fields: ClassVar = {"slug": ("heading",)}
    readonly_fields = ("preview_cover",)
    inlines = (LandingConditionInline,)

    @admin.display(description="превью обложки")
    def preview_cover(self, obj: Landing) -> str:
        return _preview(obj.cover)
