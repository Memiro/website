"""Расчёт присланной конфигурации — одна дверь для эндпоинта и заявки.

О цене конфигурации спрашивают двое: эндпоинт расчёта, которому нужен
итог для карточки, и заявка, которой нужен снимок того, что покупатель
считал. Правила у них общие — тот же гейт «товар в считаемом наборе»,
тот же перечень того, что покупатель вправе выбирать, тот же предел
производства. Разойдясь, они записали бы в заявку цену, которой
витрина не показывала, — а спор о цене решается именно снимком
(тикет 21).

Отказ отсюда уходит исключением со словами, обращёнными к посетителю:
про HTTP модуль не знает, статус ставит контроллер.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

import pydantic

from . import calculator, tariffs
from .models import SIZE_SEPARATOR, AttributeValue, Product

if TYPE_CHECKING:
    from collections.abc import Sequence

    from memiro import pricing

# Сторона изделия в запросе. Потолок — защита разбора, а не предел
# производства: тот живёт в «Параметрах расчёта» и отвечает
# приглашением к заявке, а не ошибкой
Side = Annotated[int, pydantic.Field(ge=1, le=calculator.MAX_INPUT_SIDE_MM)]

# Сколько значений справочника расчёт берёт за раз. Атрибутов у
# категории десятки, а выбирает покупатель из них меньшинство —
# список длиннее описывает не изделие, а попытку нагрузить сервер
MAX_VALUES = 50

# Один ответ на всё, что расчёту не по зубам: какая именно строка
# справочника не подошла, покупателю не объяснить, а конкуренту
# подсказало бы, чем считаемый набор ограничен
UNCALCULABLE = (
    "Такую конфигурацию сайт не считает — оставьте заявку, "
    "и менеджер назовёт цену."
)
GONE = "Такого товара больше нет в каталоге, обновите страницу."


class UncalculableError(Exception):
    """Присланное не считается — с текстом, обращённым к посетителю."""


@dataclass(frozen=True, slots=True)
class Quote:
    """Изделие, у которого спрашивают цену: товар, габариты, выбор.

    Ходят они вместе: доплата за выбор считается тем же изделием без
    этого выбора, и всё, кроме набора значений, там то же самое.
    """

    product: Product
    width_mm: int
    height_mm: int
    chosen: tuple[AttributeValue, ...]
    limits: pricing.PricingLimits

    def configuration(
        self, chosen: Sequence[AttributeValue]
    ) -> pricing.Configuration:
        return tariffs.configuration(
            self.product,
            width_mm=self.width_mm,
            height_mm=self.height_mm,
            chosen=chosen,
        )

    def price(self, chosen: Sequence[AttributeValue]) -> pricing.Price:
        return tariffs.price(self.configuration(chosen), limits=self.limits)

    def fits(self) -> bool:
        """Берётся ли производство за такой размер вообще."""
        return self.limits.fits(
            width_mm=self.width_mm, height_mm=self.height_mm
        )

    def cost(self, chosen: Sequence[AttributeValue]) -> Decimal:
        """Сумма точных статей — до порога заказа и до округления."""
        return sum(
            (line.amount for line in self.price(chosen).lines), Decimal(0)
        )

    @property
    def total(self) -> int | None:
        """Итог — или ничего, когда честного числа у конфигурации нет.

        Молчат два случая. Размер за пределом производства — личное
        пожелание, и цену ему называет менеджер. Конфигурация без
        единой платной статьи — гейт товара смотрит на его умолчания,
        а выбор покупателя ещё может обнулить единственную платную
        статью: полотно без тарифа вместо тарифицированного. Итогом
        стал бы ноль или минимальная сумма заказа — число, за которым
        ничего не стоит (тикет 19).
        """
        if not self.fits():
            return None
        price = self.price(self.chosen)
        return price.total if price.lines else None

    @property
    def label(self) -> str:
        """Конфигурация одной строкой — так её читает менеджер.

        Габариты и то, что покупатель выбрал сам; остальное описывает
        товар и читается в самом товаре. Значения подписаны атрибутом
        (`full_label`): «Осветлённое» одним словом не говорит, полотно
        это или рама.
        """
        size = f"{self.width_mm}{SIZE_SEPARATOR}{self.height_mm} мм"
        return "; ".join([size, *(value.full_label for value in self.chosen)])


def quote(
    *,
    product_id: int,
    width_mm: int,
    height_mm: int,
    value_ids: Sequence[int],
) -> Quote:
    """Собрать расчёт по присланному — или отказать словами.

    Товар берётся заново вместе со справочником: и эндпоинту, и заявке
    нужны его умолчания, а гейт спрашивается один и тот же.
    """
    product = _calculable_product(product_id)
    return Quote(
        product=product,
        width_mm=width_mm,
        height_mm=height_mm,
        chosen=_chosen(product, value_ids),
        limits=tariffs.limits_from_settings(),
    )


def _calculable_product(product_id: int) -> Product:
    """Товар, которому карточка и правда предлагает калькулятор.

    Гейт тот же, что решает судьбу блока на карточке
    (`catalog.calculator`): адрес эндпоинта открыт всякому, и разойдись
    они — сайт называл бы цену там, где витрина честно молчит.
    """
    product: Product | None = (
        Product.objects.published()
        .filter(pk=product_id)
        .prefetch_related(tariffs.product_values())
        .first()
    )
    if product is None:
        raise UncalculableError(GONE)
    if not calculator.is_calculable(product):
        raise UncalculableError(UNCALCULABLE)
    return product


def _chosen(
    product: Product, value_ids: Sequence[int]
) -> tuple[AttributeValue, ...]:
    """Выбранное покупателем — и только то, что он вправе выбирать.

    Покупатель заменяет умолчание товара, а не заводит настройку,
    которой у товара нет, — как и предпосчитанный вариант (CONTEXT.md,
    «Предпосчитанный вариант»). Товар, не назвавший атрибут вовсе, до
    расчёта не дорос: заменять нечего, и доплата за выбор оказалась бы
    полной стоимостью статьи.

    Чужой категории, неизвестное справочнику или неменяемое значение
    считать молча нельзя: посчитается не то, что показано. Два значения
    одного атрибута — тоже отказ: какое из них описывает изделие, знает
    только приславший.

    Порядок — тот же, в котором органы управления стоят на карточке:
    снимок конфигурации в заявке читается рядом с ней.
    """
    values = list(
        AttributeValue.objects.filter(pk__in=value_ids).select_related(
            "attribute"
        )
    )
    attributes = {value.attribute_id for value in values}
    if len(values) != len(set(value_ids)) or len(attributes) != len(values):
        raise UncalculableError(UNCALCULABLE)
    declared = {
        row.attribute_id
        for row in product.attribute_values.all()
        if row.value_option is not None
    }
    for value in values:
        attribute = value.attribute
        if (
            not attribute.belongs_to(product.category_id)
            or not attribute.is_customer_editable
            or attribute.pk not in declared
        ):
            raise UncalculableError(UNCALCULABLE)
    return tuple(
        sorted(
            values,
            key=lambda value: (value.attribute.order, value.attribute.name),
        )
    )
