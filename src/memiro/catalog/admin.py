from itertools import groupby
from typing import TYPE_CHECKING, Any, ClassVar

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.forms import (
    BaseInlineFormSet,
    CheckboxSelectMultiple,
    ModelChoiceField,
    ModelForm,
    ModelMultipleChoiceField,
    Select,
)
from django.forms.models import ModelChoiceIterator
from django.utils.html import format_html

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.db.models import QuerySet
    from django.db.models.fields.files import ImageFieldFile
    from django.http import HttpRequest

from memiro.singleton import SingletonAdmin
from . import calculator, tariffs
from .formatting import rub
from .models import (
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
    exhausts_dictionary,
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


class AttributeValueSelect(Select):
    """Список значений, помнящий, какому атрибуту каждое принадлежит.

    Номер атрибута нужен скрипту админки: выбрав в строке «Форму»,
    владелец должен видеть три её значения, а не весь справочник
    категории. Без скрипта разметка безвредна — список остаётся полным
    и разложенным по группам.
    """

    def create_option(
        self,
        name: str,
        value: object,
        *args: object,
        **kwargs: object,
    ) -> dict[str, Any]:
        option = super().create_option(name, value, *args, **kwargs)  # type: ignore[arg-type]
        # У пустого выбора модели за спиной нет — метить нечего
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-attribute"] = instance.attribute_id
        return option


class GroupedByAttributeIterator(ModelChoiceIterator):
    """Значения справочника, разложенные по атрибутам.

    Без групп список двусмыслен: «Серебро» в нём и тип полотна, и цвет
    рамы, и по подписи их не различить. Группа называет атрибут один
    раз, поэтому в самих подписях его нет.
    """

    def __iter__(self) -> Iterator[tuple[Any, Any]]:
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        for attribute, values in groupby(
            self.queryset, key=lambda value: value.attribute
        ):
            yield (attribute.name, [self.choice(value) for value in values])


class AttributeValueField(ModelChoiceField):
    """Значение справочника: группа называет атрибут, подпись — значение."""

    iterator = GroupedByAttributeIterator

    def label_from_instance(self, obj: AttributeValue) -> str:
        return obj.value


class ProductAttributeInline(admin.TabularInline):
    """Характеристики товара: атрибут и его значение построчно.

    Оба списка сужены до категории товара — чужого атрибута ему всё
    равно не назначить (`_check_own_category`), и держать его в выборе
    значит предлагать заведомо отвергаемое.
    """

    model = ProductAttribute
    formset = ProductAttributeFormSet
    extra = 1

    class Media:
        js = ("js/admin-attribute-values.js",)

    def get_formset(
        self,
        request: HttpRequest,
        obj: Product | None = None,
        **kwargs: object,
    ) -> type[BaseInlineFormSet]:
        formset = super().get_formset(request, obj, **kwargs)
        category_id = obj.category_id if obj else None
        fields = formset.form.base_fields
        attribute = fields["attribute"]
        if isinstance(attribute, ModelChoiceField):
            attribute.queryset = _category_attributes(category_id)
        value_option = fields["value_option"]
        fields["value_option"] = AttributeValueField(
            queryset=_category_values(category_id),
            required=False,
            label=value_option.label,
            help_text=value_option.help_text,
            widget=AttributeValueSelect,
        )
        return formset


def _category_attributes(category_id: int | None) -> QuerySet[Attribute]:
    """Атрибуты одной категории — в порядке, заданном владельцем."""
    attributes = Attribute.objects.order_by("order", "name")
    if category_id is None:
        return attributes
    return attributes.filter(category_id=category_id)


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


# Что владелец выбирает у варианта — и, главное, чего не выбирает.
# Пустое поле здесь норма, а не недозаполненность, и сказать об этом
# больше негде: в списке вариантов подписи нет
VARIANT_VALUES_HELP = (
    "Чем вариант отличается от товара. Пусто — берёт значения товара "
    "целиком. Значение заменяет умолчание товара, а не добавляется "
    "к нему; двух значений одного атрибута у варианта не бывает — "
    "это второй вариант."
)


class AttributeValueChoiceField(ModelMultipleChoiceField):
    """Значения справочника, разложенные по атрибутам.

    В списке варианта значения всех атрибутов категории лежат
    вперемешку, и `__str__` там читается двусмысленно: «Серебро» —
    и тип полотна, и цвет рамы. Атрибут называет группа, поэтому из
    подписи он убран.
    """

    iterator = GroupedByAttributeIterator

    def label_from_instance(self, obj: AttributeValue) -> str:
        return obj.value


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

    class Media:
        css: ClassVar = {"all": ("css/admin-variants.css",)}

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
            help_text=VARIANT_VALUES_HELP,
            # Флажки, а не множественный список: в списке значение
            # выбирается щелчком с Ctrl, а без него выбор молча
            # сбрасывается на одно — владельцу это стоило вечера
            widget=CheckboxSelectMultiple,
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

        Погашенная цена — третье состояние, а не второе: конструктор
        у такого товара работает, и назвать его «выключенным» значило
        бы отправить владельца искать в разметке пробел, которого там
        нет (ADR-0008). Отдельной колонки под сам признак в списке нет
        намеренно: эта строка уже говорит, что из него вышло, а два
        столбца об одном разошлись бы в первый же день, когда один
        из них забудут поправить.
        """
        # Товар в списке не сохранён — считать нечего
        if not obj.pk:
            return "—"
        missing = calculator.missing_for_calculation(obj)
        if missing:
            return "не включается: " + ", ".join(missing)
        if obj.hides_calculated_price:
            return "включён без цены: её называет менеджер"
        return "включён"

    def save_related(
        self,
        request: HttpRequest,
        form: ModelForm,
        formsets: list[Any],
        change: bool,  # noqa: FBT001 — сигнатура Django
    ) -> None:
        """Сохранить товар и сказать, если цены у него не осталось.

        Погашенная цена расчёта и отсутствие предпосчитанных вариантов
        по отдельности законны: первое — решение владельца, второе —
        обычное состояние только что заведённого товара. Вместе они
        дают карточку без единого числа, и приходит владелец к ней не
        нарочно — гасит цену у товара, вариантов которому ещё не завёл.
        Сказать об этом надо здесь: на карточке он увидел бы молчание
        и счёл его поломкой.

        Не запрет, а предупреждение: товар без цены вовсе — законное
        состояние витрины, молчание честнее заглушки (ADR-0007).

        После инлайнов, а не в `save_model`: варианты приезжают формсетом,
        и до их сохранения только что заведённый вариант ещё не в базе —
        предупреждение сработало бы на товаре, у которого цена как раз
        появилась.

        Форма списка сюда приходит тоже — Django зовёт `save_related()`
        на каждую строку пакетной правки. Признака в ней нет, и по нему
        такая форма и отличается: сняв галочку «опубликован» у двадцати
        товаров, владелец получил бы двадцать предупреждений о том, чего
        он сейчас не трогал, и перестал бы их читать.
        """
        super().save_related(request, form, formsets, change)
        if not _edits_the_whole_product(form):
            return
        product: Product = form.instance
        if product.hides_calculated_price and not product.variants.exists():
            messages.warning(
                request,
                f"«{product.name}»: цена расчёта скрыта, предпосчитанных "
                "вариантов нет — цены на сайте у этого товара не будет "
                "вовсе. Заведите варианты, если цену показать нужно.",
            )

    @admin.display(description="превью малого фото")
    def preview_small(self, obj: Product) -> str:
        return _preview(obj.photo_small)

    @admin.display(description="превью большого фото")
    def preview_large(self, obj: Product) -> str:
        return _preview(obj.photo_large)


@admin.register(PricingSettings)
class PricingSettingsAdmin(SingletonAdmin):
    """Пороги расчёта: одна строка на сайт, её правят, а не заводят."""

    list_display = ("min_area_m2", "min_order_total")


def _edits_the_whole_product(form: ModelForm) -> bool:
    """Форма карточки товара, а не строка пакетной правки списка.

    Django зовёт `save_related()` на обе, а различает их только набор
    полей: в строке списка их столько, сколько колонок в `list_editable`.
    Признак цены в неё не входит — по нему и различаем.
    """
    return "hides_calculated_price" in form.fields


def _condition_value(row: dict[str, Any]) -> object:
    """Значение, которое условие спрашивает у товара."""
    value_option = row.get("value_option")
    return value_option.pk if value_option else row.get("value_bool")


def _values_by_attribute(
    rows: list[dict[str, Any]],
) -> dict[Attribute, set[object]]:
    """Что условия спрашивают — по атрибуту, значения в кучу."""
    chosen: dict[Attribute, set[object]] = {}
    for row in rows:
        attribute = row.get("attribute")
        if attribute:
            chosen.setdefault(attribute, set()).add(_condition_value(row))
    return chosen


def _check_no_repeated_values(rows: list[dict[str, Any]]) -> None:
    """Одно значение дважды сужением не становится — это опечатка."""
    named = [row for row in rows if row.get("attribute")]
    chosen = _values_by_attribute(named)
    if sum(len(values) for values in chosen.values()) != len(named):
        message = "Одно и то же значение указано дважды."
        raise ValidationError(message)


def _check_narrows_something(rows: list[dict[str, Any]]) -> None:
    """Все значения атрибута разом — не сужение, а дубль категории."""
    for attribute, values in _values_by_attribute(rows).items():
        if exhausts_dictionary(attribute, values):
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
