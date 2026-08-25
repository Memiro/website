"""Кому карточка предлагает калькулятор и чем покупатель в нём крутит.

Гейт «товар в считаемом наборе» один на всех: его спрашивает и карточка,
решая, печатать ли калькулятор, и эндпоинт расчёта, решая, считать ли
присланное. Разъехавшись, они дали бы цену там, где витрина её честно
не показывает, — а адрес эндпоинта открыт всякому (тикет 20).

Гейта на самом деле два, и спрашивают их о разном. «Хватает ли данных»
отвечает `is_calculable()` — от него зависит сам конструктор. «Называть
ли число» отвечает `shows_calculated_price()`: к первому условию оно
добавляет признак товара, которым владелец гасит цену там, где тарифам
на этом изделии не верит. Погашенная цена конструктор не убирает —
покупатель по-прежнему говорит, чего он хочет (ADR-0008, тикет 16).

Выразить набор «полотно из четырёх видов, рама алюминиевая либо её нет»
перечнем в коде нельзя: справочник заводит владелец, и перечень
устарел бы первой же его строкой (ADR-0002). Данными сегодня
выражаются два условия, и оба обязательны:

* у товара названы все тарифицируемые атрибуты его категории,
  применимые к нему, — незаполненный значит, что цена изделия неполна;
* хотя бы одно из значений товара платное — иначе итогом был бы ноль
  или минимальная сумма заказа, число, за которым ничего не стоит.

Второе условие проверяется по умолчаниям товара; выбор покупателя
способен обнулить единственную платную статью и потом, и на это у
эндпоинта стоит своя проверка.

Багетную раму от бесплатного значения данные не отличают, и оговорку
об этом несёт ADR-0007: владелец разводит их справочником (тикет 22).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import tariffs
from .models import Attribute, AttributeValue, marks_presence

if TYPE_CHECKING:
    from collections.abc import Sequence

    from memiro import pricing
    from .models import Product, ProductVariant

# Верхняя граница ввода — защита разбора, а не предел производства:
# тот живёт в «Параметрах расчёта» и отвечает приглашением к заявке,
# а не ошибкой. Здесь отсекается разве что число в километр. Одна на
# поле карточки и на схему запроса: разойдись они, браузер пропускал
# бы то, что эндпоинт заведомо отвергнет
MAX_INPUT_SIDE_MM = 100_000

# Изделие, у которого не набралось ни одной платной статьи: итогом был
# бы ноль или минимальная сумма заказа — число, за которым ничего не
# стоит. Причина не про конкретный атрибут, и потому названа словами
NO_TARIFFS = "ни одно значение товара не тарифицировано"


@dataclass(frozen=True, slots=True)
class Value:
    """Значение справочника в списке выбора."""

    value_id: int
    label: str
    is_default: bool


@dataclass(frozen=True, slots=True)
class EditableAttribute:
    """Атрибут, который покупатель меняет, со всем его справочником.

    Подсветки, рамы и формы здесь нет — они описывают модель, и за
    другой формой покупатель идёт в другой товар (CONTEXT.md). В расчёт
    они всё равно входят: считаются от периметра, а размеры вводит
    покупатель.
    """

    name: str
    values: tuple[Value, ...]


@dataclass(frozen=True, slots=True)
class Calculator:
    """Калькулятор карточки: чем крутить и с чего начать.

    Открывается он на предпосчитанном варианте — целиком, размером и
    значениями сразу. Взять у варианта один размер значило бы показать
    на нём другую цену, чем в строке таблицы: значения вариант
    перекрывает свои. Своего размера у товара нет, и без подходящего
    варианта поля остаются пустыми — первую цену покупатель получает,
    введя свои миллиметры.
    """

    attributes: tuple[EditableAttribute, ...]
    width_mm: int | None
    height_mm: int | None
    # Называет ли карточка число. Погашенная цена оставляет органы
    # управления на месте: покупатель по-прежнему говорит, чего он
    # хочет, — а на месте цены стоит строка о менеджере (ADR-0008)
    shows_calculated_price: bool

    @property
    def max_side_mm(self) -> int:
        """Потолок полей размера — тот же, что у схемы запроса."""
        return MAX_INPUT_SIDE_MM


def for_product(
    product: Product, *, variants: Sequence[ProductVariant]
) -> Calculator | None:
    """Калькулятор товара — или ничего, если считать его нельзя."""
    if not is_calculable(product):
        return None
    defaults = _defaults(product)
    opening = _opening_variant(
        variants,
        editable=set(defaults),
        limits=tariffs.limits_from_settings(),
    )
    if opening is not None:
        defaults.update(
            {value.attribute_id: value for value in opening.values.all()}
        )
    return Calculator(
        attributes=_attributes(defaults),
        width_mm=opening.width_mm if opening else None,
        height_mm=opening.height_mm if opening else None,
        shows_calculated_price=shows_calculated_price(product),
    )


def shows_calculated_price(product: Product) -> bool:
    """Называет ли сайт цену расчёта — один ответ карточке и эндпоинту.

    Гейт цены отдельный от гейта конструктора, но такой же общий:
    карточка спрашивает его, решая, печатать ли результат, а эндпоинт —
    решая, называть ли число. Разойдись они, сайт отдавал бы цену по
    открытому всякому адресу там, где витрина честно молчит.

    Условий два, и они о разном. Данные товара отвечают, хватает ли
    их для расчёта (`is_calculable`). Признак товара отвечает, верит
    ли владелец полученному числу: изделие, где он знает, что цифра
    врёт, от считаемого данными не отличается, и без признака гасить
    цену пришлось бы порчей разметки — враньём справочнику ради
    витрины (ADR-0008).
    """
    return is_calculable(product) and not product.hides_calculated_price


def is_calculable(product: Product) -> bool:
    """Укладывается ли изделие в считаемый набор целиком."""
    return not missing_for_calculation(product)


def missing_for_calculation(product: Product) -> tuple[str, ...]:
    """Чего товару не хватает до расчёта — пусто, если хватает всего.

    Тот же гейт, что и `is_calculable()`, только вслух: владельцу в
    админке нужно не «нельзя», а «чего именно» — иначе догадываться
    о причине приходится по всему справочнику (тикет 22).
    """
    unfilled = _unfilled_attributes(product)
    if unfilled:
        return unfilled
    return () if _has_a_charged_value(product) else (NO_TARIFFS,)


def _has_a_charged_value(product: Product) -> bool:
    return any(
        value.is_charged for value in tariffs.declared_values(product).values()
    )


def _unfilled_attributes(product: Product) -> tuple[str, ...]:
    """Тарифицируемые атрибуты, которых товар не назвал.

    Спрашивается только о выборе из списка: у «да/нет» и числовых
    значения справочника нет, и их пустота цену не укорачивает.
    Незаполненный вес — не повод молчать о цене изделия, которое
    считается целиком; незаполненное количество вырезов значит, что
    вырезов нет, а не что цена неполна.

    «Полагаются» — с поправкой на зависимость: кнопки не бывает без
    подсветки или подогрева, и её отсутствие у товара без них не
    пробел. Родителем при этом бывает и «да/нет», поэтому заведённое
    считается по всем строкам товара, а не по одним тарифицируемым.
    """
    rows = list(product.attribute_values.all())
    filled = {row.attribute_id for row in rows}
    present = {
        row.attribute_id
        for row in rows
        if marks_presence(
            value_bool=row.value_bool, value_option=row.value_option
        )
    }
    return tuple(
        attribute.name
        for attribute in Attribute.objects.filter(
            category_id=product.category_id, kind=Attribute.Kind.CHOICE
        ).prefetch_related("parents")
        if attribute.pk not in filled
        and attribute.missing_parent_error(present) is None
    )


def _defaults(product: Product) -> dict[int, AttributeValue]:
    """Меняемые покупателем значения товара — по атрибуту."""
    return {
        attribute_id: value
        for attribute_id, value in tariffs.declared_values(product).items()
        if value.attribute.is_customer_editable
    }


def _opening_variant(
    variants: Sequence[ProductVariant],
    *,
    editable: set[int],
    limits: pricing.PricingLimits,
) -> ProductVariant | None:
    """Вариант, который калькулятор способен показать без расхождения.

    Вариант, перекрывший неменяемый атрибут — другую подсветку или
    раму, — калькулятор воспроизвести не может: этих списков у него
    нет. Открывшись на его размере с умолчаниями товара, он назвал бы
    на тех же параметрах не ту цену, что стоит в строке таблицы
    (ADR-0007).

    Размер за пределом производства — тот же случай с другой стороны:
    варианты владельца через предел не проходят и цену в таблице
    показывают, а калькулятор на таком размере позвал бы оставить
    заявку вместо неё.
    """
    return next(
        (
            variant
            for variant in variants
            if limits.fits(
                width_mm=variant.width_mm, height_mm=variant.height_mm
            )
            and all(
                value.attribute_id in editable
                for value in variant.values.all()
            )
        ),
        None,
    )


def _attributes(
    defaults: dict[int, AttributeValue],
) -> tuple[EditableAttribute, ...]:
    """Органы управления в порядке, заданном владельцем атрибутам."""
    dictionary = _dictionary(defaults)
    return tuple(
        EditableAttribute(
            name=default.attribute.name,
            values=tuple(
                Value(
                    value_id=value.pk,
                    label=value.value,
                    is_default=value.pk == default.pk,
                )
                for value in dictionary.get(attribute_id, ())
            ),
        )
        for attribute_id, default in sorted(
            defaults.items(),
            key=lambda pair: (
                pair[1].attribute.order,
                pair[1].attribute.name,
            ),
        )
    )


def _dictionary(
    defaults: dict[int, AttributeValue],
) -> dict[int, list[AttributeValue]]:
    """Справочник меняемых атрибутов — одним запросом на карточку."""
    values: dict[int, list[AttributeValue]] = {}
    for value in AttributeValue.objects.filter(
        attribute_id__in=list(defaults)
    ):
        values.setdefault(value.attribute_id, []).append(value)
    return values
