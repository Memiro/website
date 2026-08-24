"""JSON-эндпоинт расчёта: конфигурация → итог и подписи добавок.

В ответ уходит итоговая цена и подписи того, что покупатель выбрал
сам, с их доплатой: «Подогрев — 3 500 ₽». Ставок за метр, коэффициента
формы и разбора изделия на статьи в ответе нет — на старом сайте всё
это лежало открытым JavaScript, и повторять это нельзя (ADR-0007).

Доплата — не стоимость статьи, а разница: во сколько обошёлся сам
выбор против того, что у товара стоит по умолчанию. Так «за что
доплата» и читается покупателем, и так из ответа не восстановить
ставку: разность двух ставок ею не является, а стоимость статьи при
известном размере — является. Поэтому покупатель и вправе только
заменять умолчание товара, а не вводить настройку, которой у товара
нет: замена бесплатного платным — единственный случай, когда доплата
всё-таки равна ставке, и его ADR-0007 оговаривает отдельно.

Считается разница по точным статьям, до порога минимальной суммы
заказа и до округления итога. Иначе на изделии, упёршемся в порог,
подогрев за 3 500 ₽ показался бы доплатой в 1 000 ₽ — числом, которому
нет объяснения. Итог и доплаты отвечают на разные вопросы: сколько
платить и во сколько обошёлся выбор; на пороге они и расходятся.

Размер за пределом производства цены не получает вовсе: это личное
пожелание, и вместо числа эндпоинт зовёт оставить заявку. Предпосчитанные
варианты владельца через этот предел не проверяются — их заводит тот,
кто и знает, что производство возьмёт (`catalog.repricing`).

Метод — GET: расчёт ничего не меняет, и повторить его можно сколько
угодно раз. CSRF ему поэтому не нужен, в отличие от приёма заявки.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Annotated

import pydantic
from dmr import Controller, Query, modify
from dmr.plugins.pydantic import PydanticSerializer

from memiro.api.errors import UNPROCESSABLE, reject
from memiro.api.ids import IDS_PATTERN, MAX_IDS_LENGTH, parse_ids
from . import tariffs
from .models import AttributeValue, Product

if TYPE_CHECKING:
    from collections.abc import Sequence

    from memiro import pricing

# Верхняя граница ввода — защита разбора, а не предел производства:
# тот живёт в «Параметрах расчёта» и отвечает приглашением к заявке,
# а не ошибкой. Здесь отсекается разве что число в километр
MAX_INPUT_SIDE_MM = 100_000

Side = Annotated[int, pydantic.Field(ge=1, le=MAX_INPUT_SIDE_MM)]

# Один ответ на всё, что расчёту не по зубам: какая именно строка
# справочника не подошла, покупателю не объяснить, а конкуренту
# подсказало бы, чем считаемый набор ограничен
UNCALCULABLE = (
    "Такую конфигурацию сайт не считает — оставьте заявку, "
    "и менеджер назовёт цену."
)


class PriceQuery(pydantic.BaseModel):
    """Что считать: товар, габариты и выбранные покупателем значения."""

    product: Annotated[int, pydantic.Field(ge=1)]
    width_mm: Side
    height_mm: Side
    values: Annotated[
        str, pydantic.Field(pattern=IDS_PATTERN, max_length=MAX_IDS_LENGTH)
    ] = ""


class PriceAddition(pydantic.BaseModel):
    """Подпись выбранного с его доплатой — без ставки, из которой она.

    Доплата бывает отрицательной: покупатель вправе выбрать полотно
    дешевле того, что у товара по умолчанию, и это скидка с показанной
    цены, а не ошибка. Прятать её значило бы объяснять цену только
    тогда, когда она растёт.
    """

    label: str
    amount: int


class PriceQuote(pydantic.BaseModel):
    """Ответ расчёта: итог и то, из-за чего он такой.

    Итога может не быть: размер за пределом производства цены не
    получает, и вместо числа стоит признак «нужна заявка».
    """

    total: int | None
    additions: list[PriceAddition]
    needs_inquiry: bool


@dataclass(frozen=True, slots=True)
class _Quote:
    """Изделие, у которого спрашивают цену: товар, габариты, границы.

    Ходят они вчетвером: доплата за выбор считается тем же изделием без
    этого выбора, и всё, кроме набора значений, там то же самое.
    """

    product: Product
    width_mm: int
    height_mm: int
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


class PriceController(Controller[PydanticSerializer]):
    """Цена конфигурации: считается на сервере, тарифы наружу не идут."""

    @modify(extra_responses=[UNPROCESSABLE])
    def get(self, parsed_query: Query[PriceQuery]) -> PriceQuote:
        product = self._product(parsed_query.product)
        chosen = self._chosen(product, parse_ids(parsed_query.values))
        quote = _Quote(
            product=product,
            width_mm=parsed_query.width_mm,
            height_mm=parsed_query.height_mm,
            limits=tariffs.limits_from_settings(),
        )
        if not quote.fits():
            return PriceQuote(total=None, additions=[], needs_inquiry=True)
        price = quote.price(chosen)
        if not price.lines:
            # Ни одна статья изделия не набралась: тарифы этому товару
            # ещё не завели. Итог был бы нулём или минимальной суммой
            # заказа — числом, за которым ничего не стоит
            reject(self, UNCALCULABLE)
        return PriceQuote(
            total=price.total,
            additions=_additions(quote, chosen),
            needs_inquiry=False,
        )

    def _product(self, product_id: int) -> Product:
        product: Product | None = (
            Product.objects.published()
            .filter(pk=product_id)
            .prefetch_related(tariffs.product_values())
            .first()
        )
        if product is None:
            reject(
                self, "Такого товара больше нет в каталоге, обновите страницу."
            )
        return product

    def _chosen(
        self, product: Product, value_ids: list[int]
    ) -> list[AttributeValue]:
        """Выбранное покупателем — и только то, что он вправе выбирать.

        Покупатель заменяет умолчание товара, а не заводит настройку,
        которой у товара нет, — как и предпосчитанный вариант
        (CONTEXT.md, «Предпосчитанный вариант»). Товар, не назвавший
        атрибут вовсе, до расчёта не дорос: заменять нечего, и доплата
        за выбор оказалась бы полной стоимостью статьи.

        Чужой категории, неизвестное справочнику или неменяемое
        значение считать молча нельзя: посчитается не то, что показано.
        Два значения одного атрибута — тоже отказ: какое из них
        описывает изделие, знает только приславший.
        """
        values = list(
            AttributeValue.objects.filter(pk__in=value_ids).select_related(
                "attribute"
            )
        )
        attributes = {value.attribute_id for value in values}
        if len(values) != len(set(value_ids)) or len(attributes) != len(
            values
        ):
            reject(self, UNCALCULABLE)
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
                reject(self, UNCALCULABLE)
        return values


def _additions(
    quote: _Quote, chosen: list[AttributeValue]
) -> list[PriceAddition]:
    """Во сколько обошёлся каждый выбор покупателя.

    Разница точных статей: изделие с этим выбором минус то же изделие
    без него, где место выбора занимает умолчание товара. Не разница
    итогов: итог поднят до минимальной суммы заказа и округлён, и на
    пороге вычитание двух итогов дало бы доплату, которой нет
    объяснения.

    Выбор, ничего не изменивший, молчит — строка «0 ₽» покупателю
    ничего не объясняет.

    Расчёт зовётся заново на каждое значение, но в базу не ходит:
    и товар, и справочник уже в памяти, а движок — чистая функция.
    """
    full = quote.cost(chosen)
    additions = []
    for value in chosen:
        rest = [other for other in chosen if other.pk != value.pk]
        difference = _whole_rubles(full - quote.cost(rest))
        if difference:
            additions.append(
                PriceAddition(label=value.full_label, amount=difference)
            )
    return additions


def _whole_rubles(amount: Decimal) -> int:
    """Копейки покупателю не показывают.

    До ближайшего рубля, а не вверх, как итог: итог — то, что платят,
    и округлять его в свою пользу студия вправе; доплата же объясняет
    выбор, и врать в любую сторону ей незачем.
    """
    return int(amount.to_integral_value(rounding=ROUND_HALF_UP))
