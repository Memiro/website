"""Конструктор предпосчитанных вариантов: что владелец собрал у товара.

Вариант заводится в карточке товара конструктором: владелец ставит
размер, щёлкает значения, видит цену и жмёт «Добавить» (тикет 18).
До этого варианты правились таблицей внутри карточки, и цену владелец
узнавал только после сохранения всего товара — на зеркале с восемью
размерами это восемь кругов вслепую.

Здесь живут правила сборки и цена собранного; про HTTP модуль не
знает — отказ уходит `ValidationError` со словами, обращёнными к
владельцу, а показывает его админка.

Цену собранного спрашивают у `catalog.repricing` — у того же места,
которое запишет её варианту после сохранения. Вторым расчётом в
админке она однажды разошлась бы с записанной, и владелец добавлял
бы вариант, увидев одно число, а в таблице находил другое.

Дорога витрины (`catalog.quoting`) сюда не годится, и это не
недосмотр: она отвечает покупателю и потому спрашивает то, что к
владельцу не относится — опубликован ли товар, укладывается ли он в
считаемый набор, вправе ли покупатель менять этот атрибут и берёт ли
производство такой размер. Вариант же заводит тот, кто знает, что
производство возьмёт (CONTEXT.md), и перекрывает он любой атрибут
своей категории, а не только меняемые. Общее у них — движок и сборка
тарифов, и они общие и есть.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError

from . import calculator, tariffs
from .formatting import rub
from .models import AttributeValue, ProductVariant, check_own_category

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.db.models import QuerySet

    from .models import Product

# Потолок полей размера — тот же, что у эндпоинта расчёта. Предел
# производства это не он: тот на варианты не распространяется вовсе
MAX_SIDE_MM = calculator.MAX_INPUT_SIDE_MM

# Порядок справочника — один на всех, кто его показывает: конструктор
# вариантов, характеристики товара, экран цен. Разойдясь, они назвали
# бы владельцу одни и те же строки в разном порядке
DICTIONARY_ORDER = ("attribute__order", "attribute__name", "order", "value")

NOT_MEASURED = (
    "Укажите ширину и высоту в миллиметрах — "
    "положительными числами, каждая до "
    f"{MAX_SIDE_MM} мм."
)
UNKNOWN_VALUE = "Такого значения в справочнике больше нет — обновите страницу."
GONE = "Этого варианта у товара больше нет — обновите страницу."
NOT_ORDERED = "Порядок — целое число, начиная с нуля."
ONE_VALUE_PER_ATTRIBUTE = (
    "«%(name)s» у варианта один — заведите второй вариант."
)


def price_label(value: int) -> str:
    """Цена рублями — одинаково в списке вариантов и под конструктором.

    Печатает её браузер, а собирает сервер: разбивка тысяч у сайта
    одна (`catalog.formatting`), и третьей копии этого правила в
    скрипте админки быть не должно.
    """
    return f"{rub(value)} ₽"


@dataclass(frozen=True, slots=True)
class Composition:
    """Собранное конструктором — до того, как оно стало вариантом.

    Товар в ней есть, а `ProductVariant` ещё нет: цену владелец видит
    до сохранения, и собирать ради неё несохранённую модель значило
    бы держать в базе черновики, которых он не заводил.
    """

    product: Product
    width_mm: int
    height_mm: int
    values: tuple[AttributeValue, ...]
    # Каким по счёту вариант стоит на карточке. Не косметика: на
    # первом подходящем открывается калькулятор покупателя
    # (`calculator._opening_variant`), и отняв у владельца это поле,
    # конструктор отнял бы у него выбор стартового размера
    order: int

    @property
    def price(self) -> int:
        """Цена собранного — тем же расчётом, что запишет её варианту."""
        return tariffs.price_of(
            self.product,
            width_mm=self.width_mm,
            height_mm=self.height_mm,
            chosen=self.values,
        )


def compose(
    product: Product,
    *,
    width_mm: int,
    height_mm: int,
    value_ids: Sequence[int],
    order: int = 0,
) -> Composition:
    """Проверить собранное владельцем — или отказать словами.

    Одна дверь и для показа цены, и для сохранения: разойдись они,
    конструктор называл бы цену конфигурации, которую сам же потом
    отверг.
    """
    _measurable(width_mm, height_mm)
    return Composition(
        product=product,
        width_mm=width_mm,
        height_mm=height_mm,
        values=_values(product, value_ids),
        order=order,
    )


def save(
    composition: Composition, *, variant: ProductVariant | None = None
) -> ProductVariant:
    """Завести вариант или переписать существующий тем же собранным.

    Цена здесь не пишется: её ставит пересчёт, подписанный и на
    сохранение варианта, и на смену состава его значений
    (`catalog.repricing`). Записать её тут значило бы завести второе
    место, где цена варианта берётся.
    """
    if variant is None:
        variant = ProductVariant(product=composition.product)
    variant.width_mm = composition.width_mm
    variant.height_mm = composition.height_mm
    variant.order = composition.order
    variant.save()
    variant.values.set(composition.values)
    return variant


@dataclass(frozen=True, slots=True)
class Row:
    """Готовый вариант в списке под конструктором.

    Значения едут не только подписью, но и номерами: по ним
    конструктор открывает вариант на правку и размножает его другим
    размером, не спрашивая сервер второй раз.
    """

    variant_id: int
    width_mm: int
    height_mm: int
    order: int
    size_label: str
    values_label: str
    value_ids: tuple[int, ...]
    price: int
    price_label: str
    # Даёт ли этот вариант товару его «от X ₽». Цена товара — минимум
    # по вариантам, и одинаково дешёвых бывает несколько: помечены
    # тогда все, потому что каждый из них и правда даёт это число
    sets_product_price: bool


def rows(product: Product) -> list[Row]:
    """Варианты товара с ценами — в том порядке, в каком они на карточке."""
    existing = list(
        product.variants.prefetch_related("values__attribute").all()
    )
    cheapest = min((variant.price for variant in existing), default=None)
    return [
        Row(
            variant_id=variant.pk,
            width_mm=variant.width_mm,
            height_mm=variant.height_mm,
            order=variant.order,
            size_label=variant.size_label,
            values_label=variant.values_label or "как у товара",
            value_ids=tuple(value.pk for value in variant.values.all()),
            price=variant.price,
            price_label=price_label(variant.price),
            sets_product_price=variant.price == cheapest,
        )
        for variant in existing
    ]


def category_values(category_id: int | None) -> QuerySet[AttributeValue]:
    """Значения справочника одной категории в порядке владельца.

    Одна дорога к справочнику на всех, кто его показывает: флажки
    конструктора, списки характеристик товара, сортировка собранного.
    Без неё порядок пришлось бы повторять при каждом показе, и три
    копии однажды разошлись бы.
    """
    values = AttributeValue.objects.select_related("attribute").order_by(
        *DICTIONARY_ORDER
    )
    if category_id is None:
        return values
    return values.filter(attribute__category_id=category_id)


def dictionary(product: Product) -> list[tuple[str, list[AttributeValue]]]:
    """Справочник категории товара, разложенный по атрибутам.

    Чем вариант отличается от товара, владелец выбирает флажками, и
    выбирать ему предлагается только своё: чужую категорию `compose()`
    всё равно отвергнет, а в списке она была бы предложением заведомо
    отвергаемого.
    """
    grouped: dict[int, tuple[str, list[AttributeValue]]] = {}
    for value in category_values(product.category_id):
        _, values = grouped.setdefault(
            value.attribute_id, (value.attribute.name, [])
        )
        values.append(value)
    return list(grouped.values())


def _measurable(width_mm: int, height_mm: int) -> None:
    """Отказ владельцу в габаритах, которых расчёт не берёт.

    Само правило общее с эндпоинтом расчёта
    (`calculator.is_measurable`); разные здесь только слова отказа.
    """
    if not calculator.is_measurable(width_mm, height_mm):
        raise ValidationError(NOT_MEASURED)


def _values(
    product: Product, value_ids: Sequence[int]
) -> tuple[AttributeValue, ...]:
    """Значения варианта — и только те, что вариант вправе перекрыть.

    Правило чужой категории то же самое, что у характеристик товара
    и у условий посадочной, и живёт оно одно на всех
    (`models.check_own_category`): конструктор его не ослабляет.

    Значение, исчезнувшее из справочника, пока владелец собирал
    вариант, — не «ничего страшного»: сохранив собранное молча, сайт
    показал бы вариант, отличающийся от того, что видел владелец.

    Порядок — тот же, в котором атрибуты стоят у владельца: подпись
    варианта читается рядом со списком, из которого он собран.
    """
    ids = list(dict.fromkeys(value_ids))
    values = list(
        AttributeValue.objects.filter(pk__in=ids)
        .select_related("attribute")
        .order_by(*DICTIONARY_ORDER)
    )
    if len(values) != len(ids):
        raise ValidationError(UNKNOWN_VALUE)
    check_own_category(
        [value.attribute for value in values], product.category_id
    )
    _check_one_value_per_attribute(values)
    return tuple(values)


def _check_one_value_per_attribute(values: list[AttributeValue]) -> None:
    """Два значения одного атрибута — не вариант, а два варианта."""
    seen: set[int] = set()
    for value in values:
        if value.attribute_id in seen:
            raise ValidationError(
                ONE_VALUE_PER_ATTRIBUTE,
                params={"name": value.attribute.name},
            )
        seen.add(value.attribute_id)
