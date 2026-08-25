"""Расчёт присланной конфигурации — одна дверь для эндпоинта и заявки.

О цене конфигурации спрашивают двое: эндпоинт расчёта, которому нужен
итог для карточки, и заявка, которой нужен снимок того, что покупатель
считал. Правила у них общие — тот же гейт «товар в считаемом наборе»,
тот же признак товара, гасящий цену, тот же перечень того, что
покупатель вправе выбирать, тот же предел производства. Разойдясь,
они записали бы в заявку цену, которой витрина не показывала, — а спор
о цене решается именно снимком (тикет 21).

Отказ отсюда уходит исключением со словами, обращёнными к посетителю:
про HTTP модуль не знает, статус ставит контроллер.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property
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

# Почему у конфигурации нет цены — в самом снимке, а не догадкой
# менеджера по размеру. Причины разные: за пределом производства сайт
# цены не называет никому, а неcчитаемую конфигурацию не взял бы и
# калькулятор
BEYOND_LIMITS_NOTE = "размер за пределом производства"
NOT_COUNTED_NOTE = "эту конфигурацию сайт не считает"
# Цену расчёта владелец у этого товара погасил: конфигурация менеджеру
# нужна ровно та же, а число называет он сам (ADR-0008)
PRICE_HIDDEN_NOTE = "цену этого зеркала называет менеджер"
UNRECOGNISED_NOTE = "конфигурацию сайт не распознал"


class UncalculableError(Exception):
    """Присланное не считается — с текстом, обращённым к посетителю."""


def size_label(width_mm: int, height_mm: int) -> str:
    """Габариты строкой — как их печатает и предпосчитанный вариант."""
    return f"{width_mm}{SIZE_SEPARATOR}{height_mm} мм"


# slots нет намеренно: `total` кэшируется, а кэшу нужен __dict__.
# Цена — чистая функция от полей, и считать её трижды за запрос
# (fits, total, доплаты) незачем
@dataclass(frozen=True)
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
    # Называет ли сайт цену этого товара вообще. Тот же гейт, что
    # решает судьбу результата на карточке (`catalog.calculator`):
    # погашенная владельцем цена не должна возвращаться по открытому
    # всякому адресу эндпоинта (ADR-0008)
    shows_calculated_price: bool

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

    def surcharges(self) -> list[tuple[AttributeValue, Decimal]]:
        """Во сколько обошёлся каждый выбор покупателя.

        Разница точных статей: изделие с этим выбором минус то же
        изделие без него, где место выбора занимает умолчание товара.
        Не разница итогов: итог поднят до минимальной суммы заказа и
        округлён, и на пороге вычитание двух итогов дало бы доплату,
        которой нет объяснения.

        Расчёт зовётся заново на каждое значение, но в базу не ходит:
        и товар, и справочник уже в памяти, а движок — чистая функция.
        Округление и подпись — дело того, кто показывает.
        """
        full = self.cost(self.chosen)
        return [
            (
                value,
                full
                - self.cost(
                    [other for other in self.chosen if other.pk != value.pk]
                ),
            )
            for value in self.chosen
        ]

    @property
    def needs_inquiry(self) -> bool:
        """Случай, когда цену называет менеджер, а не сайт.

        Для покупателя размер за пределом производства и погашенная
        владельцем цена — одно и то же: числа не будет, и разговор
        идёт с менеджером. Различаются они только тем, что менеджер
        читает в снимке заявки, — и потому ответ здесь один.

        Спрашивается у самого расчёта, а не у контроллера: то же
        условие уже держит `total`, и, повторённое эндпоинтом, оно
        однажды разъехалось бы с ним — эндпоинт назвал бы цену там,
        где расчёт молчит (ADR-0008).
        """
        return not self.shows_calculated_price or not self.fits()

    @cached_property
    def total(self) -> int | None:
        """Итог — или ничего, когда честного числа у конфигурации нет.

        Молчат три случая. Товар с погашенной ценой расчёта — считать
        его сайт умеет, а называть число владелец не велел, и молчит
        здесь и расчёт заявки: снимок с ценой, которой карточка не
        показывала, спорил бы с ней (ADR-0008). Размер за пределом
        производства — личное пожелание, и цену ему называет менеджер.
        Конфигурация без единой платной статьи — гейт товара смотрит
        на его умолчания, а выбор покупателя ещё может обнулить
        единственную платную статью: полотно без тарифа вместо
        тарифицированного. Итогом стал бы ноль или минимальная сумма
        заказа — число, за которым ничего не стоит (тикет 19).
        """
        if self.needs_inquiry:
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

        Отсутствие цены строка объясняет сама: без этого «цена не
        рассчитана» у размера за пределом производства и у конфигурации,
        которую не взял бы и калькулятор, читались бы одинаково, а
        разговор с покупателем у них разный.
        """
        parts = [
            size_label(self.width_mm, self.height_mm),
            *(value.full_label for value in self.chosen),
        ]
        if not self.fits():
            parts.append(BEYOND_LIMITS_NOTE)
        elif not self.shows_calculated_price:
            parts.append(PRICE_HIDDEN_NOTE)
        elif self.total is None:
            parts.append(NOT_COUNTED_NOTE)
        return "; ".join(parts)


def unrecognised_label(width_mm: int, height_mm: int) -> str:
    """Снимок конфигурации, которой расчёт не поверил.

    Габариты покупателя в нём остаются — их прислал он сам, и
    менеджеру они нужны; за них же не ручается ничего, кроме них.
    Формат общий с `Quote.label`: снимок в журнале читается одинаково,
    посчитался он или нет.
    """
    return f"{size_label(width_mm, height_mm)}; {UNRECOGNISED_NOTE}"


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
    _measurable(width_mm, height_mm)
    product = _calculable_product(product_id)
    return Quote(
        product=product,
        width_mm=width_mm,
        height_mm=height_mm,
        chosen=_chosen(product, value_ids),
        limits=tariffs.limits_from_settings(),
        shows_calculated_price=calculator.shows_calculated_price(product),
    )


def _measurable(width_mm: int, height_mm: int) -> None:
    """Отказ покупателю в габаритах, которых расчёт не берёт.

    Само правило общее с конструктором вариантов
    (`calculator.is_measurable`) — разные здесь только слова отказа:
    посетителю сайт объясняет, что делать дальше.

    Проверяется тут, а не схемой запроса, чтобы заявке было что
    делать с таким числом, кроме как потерять её вместе с контактами.
    """
    if not calculator.is_measurable(width_mm, height_mm):
        raise UncalculableError(UNCALCULABLE)


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

    Потолок длины списка стоит здесь же: он один на эндпоинт цены и
    на заявку, а разойдись они — «одна дверь» осталась бы словами.
    """
    if len(value_ids) > MAX_VALUES:
        raise UncalculableError(UNCALCULABLE)
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
