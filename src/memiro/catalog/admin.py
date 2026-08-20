from typing import TYPE_CHECKING, Any, ClassVar

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet
from django.utils.html import format_html

if TYPE_CHECKING:
    from django.db.models.fields.files import ImageFieldFile

from .models import (
    MAX_LANDING_CONDITIONS,
    Attribute,
    AttributeValue,
    Category,
    Landing,
    LandingCondition,
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


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "kind", "order")
    list_filter = ("category", "kind")
    list_editable = ("order",)
    prepopulated_fields: ClassVar = {"slug": ("name",)}
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


def _check_own_category(
    rows: list[dict[str, Any]], category_id: int | None
) -> None:
    """Атрибуты чужой категории в инлайне — ошибка.

    Пока родитель не сохранён, model.clean его категории не видит,
    поэтому проверка живёт в формсете.
    """
    if not category_id:
        return
    for row in rows:
        attribute = row.get("attribute")
        if attribute and not attribute.belongs_to(category_id):
            message = "Атрибут «%(name)s» принадлежит другой категории."
            raise ValidationError(message, params={"name": attribute.name})


class ProductAttributeFormSet(BaseInlineFormSet):
    def clean(self) -> None:
        super().clean()
        _check_own_category(_kept_rows(self), self.instance.category_id)


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
        _check_own_category(kept, self.instance.category_id)


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
