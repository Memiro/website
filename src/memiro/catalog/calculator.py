"""Кому карточка предлагает калькулятор и чем покупатель в нём крутит.

Гейт «товар в считаемом наборе» один на всех: его спрашивает и карточка,
решая, печатать ли калькулятор, и эндпоинт расчёта, решая, считать ли
присланное. Разъехавшись, они дали бы цену там, где витрина её честно
не показывает, — а адрес эндпоинта открыт всякому (тикет 20).

Выразить набор «полотно из четырёх видов, рама алюминиевая либо её нет»
перечнем в коде нельзя: справочник заводит владелец, и перечень
устарел бы первой же его строкой (ADR-0002). Данными сегодня
выражаются два условия, и оба обязательны:

* у товара заполнены все атрибуты его категории, применимые к нему, —
  незаполненный атрибут значит, что изделие ещё не описано целиком;
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

from .models import Attribute, AttributeValue

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from .models import Product, ProductAttribute, ProductVariant

# Верхняя граница ввода — защита разбора, а не предел производства:
# тот живёт в «Параметрах расчёта» и отвечает приглашением к заявке,
# а не ошибкой. Здесь отсекается разве что число в километр. Одна на
# поле карточки и на схему запроса: разойдись они, браузер пропускал
# бы то, что эндпоинт заведомо отвергнет
MAX_INPUT_SIDE_MM = 100_000


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
    opening = _opening_variant(variants, editable=set(defaults))
    if opening is not None:
        defaults.update(
            {value.attribute_id: value for value in opening.values.all()}
        )
    return Calculator(
        attributes=_attributes(defaults),
        width_mm=opening.width_mm if opening else None,
        height_mm=opening.height_mm if opening else None,
    )


def is_calculable(product: Product) -> bool:
    """Укладывается ли изделие в считаемый набор целиком."""
    rows = list(product.attribute_values.all())
    return _has_a_charged_value(rows) and _is_described_fully(product, rows)


def _has_a_charged_value(rows: Iterable[ProductAttribute]) -> bool:
    return any(
        row.value_option is not None and row.value_option.is_charged
        for row in rows
    )


def _is_described_fully(
    product: Product, rows: Sequence[ProductAttribute]
) -> bool:
    """Заведены ли у товара все атрибуты категории, которые ему полагаются.

    «Полагаются» — с поправкой на зависимость: кнопки не бывает без
    подсветки или подогрева, и её отсутствие у товара без них не
    пробел. Признак «да/нет» со значением «нет» родителем не считается,
    как и в проверке админки.
    """
    filled = {row.attribute_id for row in rows}
    present = {row.attribute_id for row in rows if row.value_bool is not False}
    return not any(
        attribute.pk not in filled
        and attribute.missing_parent_error(present) is None
        for attribute in Attribute.objects.filter(
            category_id=product.category_id
        ).prefetch_related("parents")
    )


def _defaults(product: Product) -> dict[int, AttributeValue]:
    """Меняемые покупателем значения товара — по атрибуту.

    Атрибут берётся у значения, а не у строки товара: расчёт и так
    загружает `value_option__attribute`, и второй раз спрашивать базу
    об одном и том же незачем.
    """
    return {
        row.value_option.attribute_id: row.value_option
        for row in product.attribute_values.all()
        if row.value_option is not None
        and row.value_option.attribute.is_customer_editable
    }


def _opening_variant(
    variants: Sequence[ProductVariant], *, editable: set[int]
) -> ProductVariant | None:
    """Вариант, который калькулятор способен показать без расхождения.

    Вариант, перекрывший неменяемый атрибут — другую подсветку или
    раму, — калькулятор воспроизвести не может: этих списков у него
    нет. Открывшись на его размере с умолчаниями товара, он назвал бы
    на тех же параметрах не ту цену, что стоит в строке таблицы
    (ADR-0007).
    """
    return next(
        (
            variant
            for variant in variants
            if all(
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
    options = _options(defaults)
    return tuple(
        EditableAttribute(
            name=default.attribute.name,
            values=tuple(
                Value(
                    value_id=value.pk,
                    label=value.value,
                    is_default=value.pk == default.pk,
                )
                for value in options.get(attribute_id, ())
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


def _options(
    defaults: dict[int, AttributeValue],
) -> dict[int, list[AttributeValue]]:
    """Справочник меняемых атрибутов — одним запросом на карточку."""
    options: dict[int, list[AttributeValue]] = {}
    for value in AttributeValue.objects.filter(
        attribute_id__in=list(defaults)
    ):
        options.setdefault(value.attribute_id, []).append(value)
    return options
