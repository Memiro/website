from dataclasses import asdict
from http import HTTPStatus
from itertools import groupby
from typing import TYPE_CHECKING, Any, ClassVar

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.forms import (
    BaseInlineFormSet,
    ModelChoiceField,
    ModelForm,
    Select,
)
from django.forms.models import ModelChoiceIterator
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.views.decorators.http import require_POST

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.db.models import QuerySet
    from django.db.models.fields.files import ImageFieldFile
    from django.http import HttpRequest, HttpResponse, QueryDict
    from django.urls import URLPattern

from memiro.singleton import SingletonAdmin
from . import calculator, tariffs, variants
from .formatting import rub
from .models import (
    FOREIGN_CATEGORY,
    MAX_LANDING_ATTRIBUTES,
    Attribute,
    AttributeValue,
    Category,
    Landing,
    LandingCondition,
    MaterialPrice,
    PricingSettings,
    Product,
    ProductAttribute,
    ProductImage,
    ProductVariant,
    check_own_category,
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
        check_own_category(_attributes(rows), self.instance.category_id)
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
    равно не назначить (`check_own_category`), и держать его в выборе
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
            queryset=variants.category_values(category_id),
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


# Адреса конструктора вариантов: три действия под карточкой товара.
# Имена нужны шаблону — он печатает их в разметку, чтобы маршруты
# Django не переписывались в браузере
VARIANT_PRICE_URL = "catalog_product_variant_price"
VARIANT_SAVE_URL = "catalog_product_variant_save"
VARIANT_DELETE_URL = "catalog_product_variant_delete"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Карточка товара — и конструктор вариантов под ней (тикет 18).

    Таблицы вариантов в карточке больше нет: цену она называла только
    после сохранения всего товара, и на зеркале с восемью размерами
    владелец ходил восемь кругов вслепую. Конструктор показывает цену
    до сохранения и заводит вариант, не трогая остальную карточку.

    Живёт он внутри карточки, а не своим разделом админки: вариант без
    товара не существует — это точка расчёта, а не товар (CONTEXT.md).
    """

    change_form_template = "admin/catalog/product/change_form.html"

    class Media:
        js: ClassVar = ("js/admin-variant-builder.js",)
        css: ClassVar = {"all": ("css/admin-variants.css",)}

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
    )

    def get_urls(self) -> list[URLPattern]:
        """Три адреса конструктора — перед адресами самой админки.

        После них не выйдет: `<path:object_id>/` ловит что угодно,
        и «варианты» уехали бы в карточку товара с таким номером.
        """
        own = [
            path(
                "<int:product_id>/variants/price/",
                self.admin_site.admin_view(self.variant_price_view),
                name=VARIANT_PRICE_URL,
            ),
            path(
                "<int:product_id>/variants/save/",
                self.admin_site.admin_view(self.variant_save_view),
                name=VARIANT_SAVE_URL,
            ),
            path(
                "<int:product_id>/variants/delete/",
                self.admin_site.admin_view(self.variant_delete_view),
                name=VARIANT_DELETE_URL,
            ),
        ]
        return own + super().get_urls()

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        """Кладёт конструктор в карточку сохранённого товара.

        Только в неё: у товара, которого ещё нет, конструктора нет
        тоже — вариант без товара не существует, а цену его не
        посчитать, она складывается из атрибутов, которых товар пока
        не назвал. На странице заведения признака в контексте нет
        вовсе, и шаблон говорит там, что делать дальше.

        Нет его и у того, кто карточку только смотрит: адреса
        конструктора спрашивают право на правку, и нарисованные ему
        поля с кнопками были бы предложением заведомо отвергаемого.
        """
        product: Product | None = self.get_object(request, object_id)
        builder = (
            _builder_context(product)
            if product is not None
            and self.has_change_permission(request, product)
            else None
        )
        return super().change_view(
            request,
            object_id,
            form_url,
            {**(extra_context or {}), "variant_builder": builder},
        )

    def variant_price_view(
        self, request: HttpRequest, product_id: int
    ) -> JsonResponse:
        """Цена собранного — до того, как владелец нажал «Добавить».

        Считается тем же расчётом, что запишет её варианту, и потому
        совпадает с ней по построению (`catalog.variants`).
        """
        product = self._variant_product(request, product_id)
        try:
            composition = _composed(request.GET, product)
        except ValidationError as refusal:
            return _refusal(refusal)
        price = composition.price
        return JsonResponse(
            {"price": price, "price_label": variants.price_label(price)}
        )

    @method_decorator(require_POST)
    def variant_save_view(
        self, request: HttpRequest, product_id: int
    ) -> JsonResponse:
        """Завести вариант или переписать тот, что владелец правит.

        В ответ уходит весь список: «от X ₽» товара берётся минимумом
        по вариантам, и один заведённый вариант меняет пометку у
        другого. Собирать список в браузере значило бы считать этот
        минимум второй раз.
        """
        product = self._variant_product(request, product_id)
        try:
            variant = _named_variant(request.POST, product)
            composition = _composed(request.POST, product)
        except ValidationError as refusal:
            return _refusal(refusal)
        variants.save(composition, variant=variant)
        return _rows_response(product)

    @method_decorator(require_POST)
    def variant_delete_view(
        self, request: HttpRequest, product_id: int
    ) -> JsonResponse:
        """Удалить вариант товара — и вернуть список, каким он стал."""
        product = self._variant_product(request, product_id)
        try:
            variant = _named_variant(request.POST, product)
        except ValidationError as refusal:
            return _refusal(refusal)
        if variant is not None:
            variant.delete()
        return _rows_response(product)

    def _variant_product(
        self, request: HttpRequest, product_id: int
    ) -> Product:
        """Товар, варианты которого этот пользователь вправе править.

        Права спрашиваются те же, что у самой карточки: конструктор —
        её часть, и своего доступа у него нет. Удаление варианта —
        тоже правка карточки, а не удаление товара, и права у него
        те же: сам товар остаётся на месте.
        """
        product: Product | None = self.get_object(request, str(product_id))
        if product is None or not self.has_change_permission(request, product):
            raise PermissionDenied
        return product

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


def _builder_context(product: Product) -> dict[str, Any]:
    """Всё, из чего шаблон рисует конструктор.

    Адреса приезжают готовыми: собирать их в браузере значило бы
    держать вторую копию маршрутов Django, которая рассохнется первой
    же правкой `get_urls()`.
    """
    return {
        "groups": variants.dictionary(product),
        "values_help": variants.VALUES_HELP,
        "rows": _variant_rows(product),
        "max_side_mm": calculator.MAX_INPUT_SIDE_MM,
        "price_url": _variant_url(VARIANT_PRICE_URL, product),
        "save_url": _variant_url(VARIANT_SAVE_URL, product),
        "delete_url": _variant_url(VARIANT_DELETE_URL, product),
    }


def _variant_url(name: str, product: Product) -> str:
    return reverse(f"admin:{name}", args=[product.pk])


def _variant_rows(product: Product) -> list[dict[str, Any]]:
    """Варианты товара так, как их читает скрипт конструктора.

    Одним и тем же видом при первой отрисовке и после каждой правки:
    вторая форма того же списка разошлась бы с первой.
    """
    return [asdict(row) for row in variants.rows(product)]


def _rows_response(product: Product) -> JsonResponse:
    """Список вариантов таким, каким он стал после правки."""
    return JsonResponse({"variants": _variant_rows(product)})


def _refusal(error: ValidationError) -> JsonResponse:
    """Отказ конструктора — словами, обращёнными к владельцу.

    Код тот же, что у отказов витрины: форма запроса верна, а
    собранное правилам не отвечает. Форма ответа своя, а не
    `api.errors.ErrorModel`: та живёт у контроллеров dmr, а
    конструктор — обычная вьюха админки, и заводить ради него
    контроллер значило бы тащить весь слой API в админку. Читает
    этот ответ один-единственный скрипт — тот, что рядом.
    """
    return JsonResponse(
        {"error": " ".join(error.messages)},
        status=HTTPStatus.UNPROCESSABLE_ENTITY,
    )


def _composed(data: QueryDict, product: Product) -> variants.Composition:
    """Собранное владельцем — из того, что прислала страница.

    Разбор один на показ цены и на сохранение: разойдись они,
    конструктор назвал бы цену конфигурации, которую сам же потом
    отверг. Живёт он в `catalog.variants`, рядом со словами отказа;
    здесь остаётся достать поля из запроса.
    """
    return variants.compose_from(
        product=product,
        width_mm=data.get("width_mm"),
        height_mm=data.get("height_mm"),
        value_ids=data.getlist("values"),
        order=data.get("order"),
    )


def _named_variant(data: QueryDict, product: Product) -> ProductVariant | None:
    """Вариант, который запрос назвал, — или ничего, если не назвал.

    Называют его правка и удаление; заведение — нет, ему нечего
    называть.

    Чужой товару вариант сюда не попадает: спрашивается он у самого
    товара, и подменённый номер отвечает тем же, что и удалённый.
    """
    raw = data.get("variant", "")
    if not raw:
        return None
    variant = (
        product.variants.filter(pk=int(raw)).first() if raw.isdigit() else None
    )
    if variant is None:
        raise ValidationError(variants.GONE)
    return variant


# Пункт фильтра, которого нет среди единиц расхода: пустую строку
# `choices` не знает, а искать значения без тарифа владельцу нужно
NO_TARIFF = "none"

# Имя пометки на запросе: сказано ли в нём о пересчёте. Пачкой правят
# по два десятка строк, и двадцать одинаковых сообщений перестают читать
REPRICING_ANNOUNCED_ATTR = "_memiro_repricing_announced"

# Что на экране цен правится, а что только показывается. Одной тройкой
# на форму и на список: разойдясь, они дали бы строку, поля которой
# правила справочника не проверяют
PRICE_COLUMNS = ("unit", "rate", "scaled_by_shape")


class MaterialPriceForm(ModelForm):
    """Строка экрана цен: правила справочника целиком, полей меньше.

    `AttributeValue.clean()` умеет указать на `value` и на
    `marks_absence` — поля, которых в строке списка нет. Django на
    ошибку по чужому полю отвечает `ValueError` и роняет страницу,
    поэтому такая ошибка показывается строкой целиком: правило должно
    звучать, а не падать.
    """

    class Meta:
        model = MaterialPrice
        fields = PRICE_COLUMNS

    # `Any` — потому что в базе метод перегружен: поле с ошибкой
    # приходит и строкой, и None, и словарём, и сузить это здесь
    # значило бы отвергнуть половину вызовов Django
    def add_error(self, field: Any, error: Any) -> None:  # noqa: ANN401
        if field is not None or not hasattr(error, "error_dict"):
            super().add_error(field, error)
            return
        own = {
            name: found
            for name, found in error.error_dict.items()
            if name in self.fields
        }
        foreign = [
            message
            for name, found in error.error_dict.items()
            if name not in self.fields
            for message in found
        ]
        if foreign:
            super().add_error(None, foreign)
        if own:
            super().add_error(None, own)


class UnitOrNoTariffFilter(admin.SimpleListFilter):
    """Единица расхода — и отдельным пунктом отсутствие тарифа.

    425 значений переехали со старого сайта до заведения тарифов, и
    «бесплатно» от «руки не дошли» в данных не отличить: отличает их
    владелец, глядя на список (тикет 17). Пункт «тариф не заведён»
    собирает такие строки в одно место — обычный фильтр по полю его
    не даёт, пустая строка среди `choices` не значится.

    Половина тарифа собирается туда же: статьи расхода она не даёт
    (`AttributeValue.is_charged`), а в списке выглядит заполненной —
    и мимо этого пункта не нашлась бы никогда.
    """

    title = "единица расхода"
    parameter_name = "unit"

    def lookups(
        self,
        request: HttpRequest,  # noqa: ARG002 — сигнатура Django
        model_admin: admin.ModelAdmin,  # noqa: ARG002 — сигнатура Django
    ) -> tuple[tuple[str, str], ...]:
        return (
            *AttributeValue.Unit.choices,
            (NO_TARIFF, "тариф не заведён"),
        )

    def queryset(
        self,
        request: HttpRequest,  # noqa: ARG002 — сигнатура Django
        queryset: QuerySet[MaterialPrice],
    ) -> QuerySet[MaterialPrice]:
        chosen = self.value()
        if chosen is None:
            return queryset
        if chosen == NO_TARIFF:
            return queryset.filter(Q(unit="") | Q(rate__isnull=True))
        return queryset.filter(unit=chosen)


@admin.register(MaterialPrice)
class MaterialPriceAdmin(admin.ModelAdmin):
    """Все платные строки справочника одним плоским списком.

    Экран не заводит второй правды о цене: это тот же справочник,
    показанный поперёк атрибутов (ADR-0007). Движок расчёта, сборка
    тарифов и пересчёт он не трогает — только даёт до них дойти.

    Поиск ищет по названию значения, а не по атрибуту: атрибут в этом
    списке спрашивают фильтром, и вторая дорога к тому же сужению
    сделала бы выдачу поиска необъяснимой.
    """

    form = MaterialPriceForm
    list_display = ("value", "attribute", *PRICE_COLUMNS)
    list_display_links = ("value",)
    list_editable = PRICE_COLUMNS
    list_filter = (
        ("attribute", admin.RelatedOnlyFieldListFilter),
        UnitOrNoTariffFilter,
    )
    search_fields = ("value",)
    ordering = ("attribute__order", "attribute__name", "order", "value")
    # На странице одной строки те же три поля, что и в списке, — но
    # там они стоят без подписи, чьи они: «за м², 4 000» одинаково
    # читается у полотна и у рамы. Атрибут и значение её и называют,
    # а правятся они там же, где заводятся, — у атрибута
    fields = ("attribute", "value", *PRICE_COLUMNS)
    readonly_fields = ("attribute", "value")

    def get_queryset(self, request: HttpRequest) -> QuerySet[MaterialPrice]:
        """Строки, которые стоят денег или могут начать стоить.

        Отсутствие признака — «без рамы», «без подсветки» — денег не
        стоит и по правилу `clean()` стоить не может: держать пустое
        такое значение на экране цен значило бы предлагать заведомо
        отвергаемое.

        Кроме одного случая: если ставка на нём всё-таки стоит.
        `clean()` мимо переносов и пачечных правок проходит, а движок
        цены о признаке отсутствия не спрашивает — такая строка берёт
        деньги молча, и чинить её надо там, где чинят цены. Здесь она
        видна, и правило говорит о ней словами.
        """
        return (
            super()
            .get_queryset(request)
            .select_related("attribute")
            .exclude(marks_absence=True, unit="", rate__isnull=True)
        )

    def has_add_permission(
        self,
        request: HttpRequest,  # noqa: ARG002 — сигнатура Django
    ) -> bool:
        """Значения заводят у их атрибута, а не здесь.

        Строка справочника — это атрибут и значение; на экране цен их
        обоих нет, и заводить строку тут значило бы спрашивать о
        справочнике посреди разговора о деньгах. Удаление закрыто по
        той же причине, и заодно потому, что удалить с экрана цен
        значение, на которое опирается товар, слишком легко.
        """
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,  # noqa: ARG002 — сигнатура Django
        obj: MaterialPrice | None = None,  # noqa: ARG002 — сигнатура Django
    ) -> bool:
        """Причина та же, что и у `has_add_permission()`."""
        return False

    def get_changelist_form(
        self, request: HttpRequest, **kwargs: object
    ) -> type[ModelForm]:
        """Строку списка правит форма экрана, а не голая `ModelForm`.

        Иначе правила справочника, указавшие на поле вне строки,
        уронили бы страницу пакетной правки.
        """
        return super().get_changelist_form(request, form=self.form, **kwargs)

    def save_model(
        self,
        request: HttpRequest,
        obj: MaterialPrice,
        form: ModelForm,
        change: bool,  # noqa: FBT001 — сигнатура Django
    ) -> None:
        """Сохранить строку тем классом, которым она живёт, — и сказать.

        Пересчёт подписан на `AttributeValue` (`repricing.connect()`),
        а прокси шлёт сигналы от своего имени: сохранённая от имени
        экрана строка оставила бы цены старыми, и молча.

        И вернуть класс обратно: историю правок админка пишет после
        сохранения и кладёт её на тот класс, которым объект назвался.
        Уехав вместе с сигналом, история легла бы мимо экрана — и
        «История» у строки цен всегда была бы пуста.
        """
        obj.__class__ = AttributeValue  # type: ignore[assignment]
        super().save_model(request, obj, form, change)
        obj.__class__ = MaterialPrice
        self._announce_repricing(request)

    def _announce_repricing(self, request: HttpRequest) -> None:
        """Сказать, что правка тарифа доехала до цен.

        Пересчёт молчалив: владелец, поднявший цену полотна, видит
        только «изменено 1 значение» и уходит проверять карточки
        руками. Считается он здесь же, в сохранении, — сообщение
        говорит о том, что уже случилось, а не обещает.
        """
        if getattr(request, REPRICING_ANNOUNCED_ATTR, False):
            return
        setattr(request, REPRICING_ANNOUNCED_ATTR, True)
        message = (
            "Цены пересчитаны: тариф проехал по всем предпосчитанным "
            "вариантам, а цены товаров взяты по самому дешёвому из них."
            if ProductVariant.objects.exists()
            else "Предпосчитанных вариантов пока нет — пересчитывать нечего."
        )
        messages.info(request, message)


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
        check_own_category(attributes, self.instance.category_id)
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
