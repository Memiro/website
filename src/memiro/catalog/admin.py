from typing import TYPE_CHECKING, ClassVar

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet
from django.utils.html import format_html

if TYPE_CHECKING:
    from django.db.models.fields.files import ImageFieldFile

from .models import (
    Attribute,
    AttributeValue,
    Category,
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


class ProductAttributeFormSet(BaseInlineFormSet):
    def clean(self) -> None:
        """Атрибуты чужой категории режем и при создании товара,

        когда сам товар ещё не сохранён и model.clean его не видит.
        """
        super().clean()
        category_id = self.instance.category_id
        if not category_id:
            return
        for form in self.forms:
            # Помеченные на удаление строки не проверяем: смена
            # категории товара с удалением старых атрибутов — один шаг
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            attribute = form.cleaned_data.get("attribute")
            if attribute and not attribute.belongs_to(category_id):
                message = "Атрибут «%(name)s» принадлежит другой категории."
                raise ValidationError(
                    message,
                    params={"name": attribute.name},
                )


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
