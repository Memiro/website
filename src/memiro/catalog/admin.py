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

from . import calculator, tariffs
from .formatting import rub
from .models import (
    BOOL_TOKENS,
    MAX_LANDING_ATTRIBUTES,
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
        "is_filterable",
        "order",
    )
    list_filter = (
        "category",
        "kind",
        "is_customer_editable",
        "is_filterable",
    )
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
    при незаведённом подогреве. Выбор из списка говорит о том же
    своим значением — «без рамы», «без подсветки» (CONTEXT.md,
    тикет 22).
    """
    return {
        row["attribute"].pk
        for row in rows
        if row.get("attribute")
        and marks_presence(
            value_bool=row.get("value_bool"),
            value_option=row.get("value_option"),
        )
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
        "calculator_state",
        "is_published",
        "is_popular",
        "is_promo",
        "order",
    )
    list_filter = ("category", "is_published", "is_popular", "is_promo")
    list_editable = ("is_published", "is_popular", "is_promo", "order")
    search_fields = ("name", "article")
    prepopulated_fields: ClassVar = {"slug": ("name",)}
    readonly_fields = (
        "price_explained",
        "calculator_state",
        "preview_small",
        "preview_large",
    )
    inlines = (
        ProductImageInline,
        ProductAttributeInline,
        ProductVariantInline,
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Product]:
        """Значения атрибутов — одним запросом на список.

        Их читает колонка расчёта, и без префетча каждая строка
        ходила бы за ними сама. Справочник категории она всё равно
        спрашивает построчно: он у товаров общий, но знает об этом
        только гейт, а не список.
        """
        return (
            super()
            .get_queryset(request)
            .prefetch_related(tariffs.product_values())
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

    @admin.display(description="калькулятор")
    def calculator_state(self, obj: Product) -> str:
        """Что мешает товару считаться — списком, а не молчанием.

        После переразметки справочника у 88 перенесённых зеркал не
        хватает вида подсветки, температуры и типа полотна, и владелец
        проставляет их по одному (тикет 22). Без этой строки он видел
        бы только отсутствие калькулятора на карточке и гадал, чего
        именно недостаёт.
        """
        # Товар в списке не сохранён — считать нечего
        if not obj.pk:
            return "—"
        missing = calculator.missing_for_calculation(obj)
        if not missing:
            return "включён"
        return "не включается: " + ", ".join(missing)

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


def _condition_key(row: dict[str, Any]) -> tuple[int, object]:
    """Что именно условие спрашивает у товара: атрибут и значение."""
    return (
        row["attribute"].pk,
        row["value_option"].pk
        if row.get("value_option")
        else row.get("value_bool"),
    )


def _check_no_repeated_values(rows: list[dict[str, Any]]) -> None:
    """Одно значение дважды сужением не становится — это опечатка."""
    keys = [_condition_key(row) for row in rows if row.get("attribute")]
    if len(keys) != len(set(keys)):
        message = "Одно и то же значение указано дважды."
        raise ValidationError(message)


def _check_narrows_something(rows: list[dict[str, Any]]) -> None:
    """Все значения атрибута разом — не сужение, а дубль категории.

    Значения одного атрибута объединяются по ИЛИ, и перечислив их все,
    владелец получил бы под своим адресом весь каталог категории —
    ровно тот индексируемый дубль, ради которого ADR-0003 и завёл
    ручной список посадочных.
    """
    chosen: dict[Attribute, set[object]] = {}
    for row in rows:
        attribute = row.get("attribute")
        if attribute:
            chosen.setdefault(attribute, set()).add(_condition_key(row)[1])
    for attribute, values in chosen.items():
        available = (
            attribute.values.count()
            if attribute.kind == Attribute.Kind.CHOICE
            else len(BOOL_TOKENS)
        )
        if len(values) >= available:
            message = (
                "«%(name)s»: перечислены все значения — "
                "такая страница ничего не сужает."
            )
            raise ValidationError(message, params={"name": attribute.name})


class LandingConditionFormSet(BaseInlineFormSet):
    def clean(self) -> None:
        """Посадочная — категория и один-два сужающих атрибута (ADR-0003).

        Без условий это дубль категории, с длинным хвостом — мусор
        в индексе. Значений у атрибута бывает несколько: они
        объединяются по ИЛИ и хвоста не удлиняют.
        """
        super().clean()
        kept = _kept_rows(self)
        if not kept:
            message = "Добавьте хотя бы одно условие."
            raise ValidationError(message)
        attributes = _attributes(kept)
        narrowing = {attribute.pk for attribute in attributes}
        if len(narrowing) > MAX_LANDING_ATTRIBUTES:
            message = "Сужайте не больше чем %(limit)s атрибутами."
            raise ValidationError(
                message, params={"limit": MAX_LANDING_ATTRIBUTES}
            )
        _check_own_category(attributes, self.instance.category_id)
        _check_no_repeated_values(kept)
        _check_narrows_something(kept)


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
