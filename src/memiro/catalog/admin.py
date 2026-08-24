from typing import TYPE_CHECKING, Any, ClassVar

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import (
    BaseInlineFormSet,
    ModelForm,
    ModelMultipleChoiceField,
)
from django.utils.html import format_html

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.db.models.fields.files import ImageFieldFile
    from django.http import HttpRequest

from .formatting import rub
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
    ProductVariant,
    marks_presence,
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
        if row.get("attribute")
        and marks_presence(value_bool=row.get("value_bool"))
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


def _check_one_value_per_attribute(values: list[AttributeValue]) -> None:
    """Два значения одного атрибута — не вариант, а два варианта."""
    seen: set[int] = set()
    for value in values:
        if value.attribute_id in seen:
            message = "«%(name)s» у варианта один — заведите второй вариант."
            raise ValidationError(
                message, params={"name": value.attribute.name}
            )
        seen.add(value.attribute_id)


class ProductVariantFormSet(BaseInlineFormSet):
    def clean(self) -> None:
        super().clean()
        for row in _kept_rows(self):
            values = list(row.get("values") or ())
            attributes = [value.attribute for value in values]
            _check_own_category(attributes, self.instance.category_id)
            _check_one_value_per_attribute(values)


class AttributeValueChoiceField(ModelMultipleChoiceField):
    """Значения справочника с названием атрибута в подписи.

    В списке варианта значения всех атрибутов категории лежат
    вперемешку, и `__str__` там читается двусмысленно.
    """

    def label_from_instance(self, obj: AttributeValue) -> str:
        return obj.full_label


def _category_values(category_id: int | None) -> QuerySet[AttributeValue]:
    """Значения справочника одной категории, сгруппированные атрибутом."""
    values = AttributeValue.objects.select_related("attribute").order_by(
        "attribute__order", "attribute__name", "order", "value"
    )
    if category_id is None:
        return values
    return values.filter(attribute__category_id=category_id)


class ProductVariantInline(admin.TabularInline):
    """Предпосчитанные варианты правятся в карточке товара.

    Цены среди полей нет: её считает движок из справочника, и вторая
    правда о цене товару не нужна (тикет 17).
    """

    model = ProductVariant
    formset = ProductVariantFormSet
    extra = 1
    readonly_fields = ("computed_price",)

    def get_formset(
        self,
        request: HttpRequest,
        obj: Product | None = None,
        **kwargs: object,
    ) -> type[BaseInlineFormSet]:
        """Выбирать вариант можно только из атрибутов своей категории.

        У ещё не заведённого товара категории нет — там список полный,
        а чужое значение отвергает формсет.
        """
        formset = super().get_formset(request, obj, **kwargs)
        values = formset.form.base_fields["values"]
        formset.form.base_fields["values"] = AttributeValueChoiceField(
            queryset=_category_values(obj.category_id if obj else None),
            required=False,
            label=values.label,
            widget=values.widget,
        )
        return formset

    @admin.display(description="цена (считается по тарифам)")
    def computed_price(self, obj: ProductVariant) -> str:
        # Пустая строка инлайна ещё не сохранена — считать нечего
        if not obj.pk:
            return "—"
        return f"{rub(obj.price)} ₽"


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
    readonly_fields = ("price_explained", "preview_small", "preview_large")
    inlines = (
        ProductImageInline,
        ProductAttributeInline,
        ProductVariantInline,
    )

    @admin.display(description="цена «от»")
    def price_explained(self, obj: Product) -> str:
        """Цену владелец не вводит: её даёт самый дешёвый вариант.

        `editable=False` убирает поле из формы молча — а молчание тут
        читается как «цену забыли». Строка объясняет, откуда число
        берётся и что делать, когда его нет.
        """
        # `is None`, а не `has_price`: здесь же цена и печатается,
        # и проверку типов устраивает только сужение по самому полю
        if obj.price is None:
            return (
                "—  цена появится, когда у товара будет хотя бы один "
                "предпосчитанный вариант"
            )
        return f"{rub(obj.price)} ₽  — по самому дешёвому варианту"

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
