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

Разбор присланного и сам расчёт живут в `catalog.quoting` — те же
правила спрашивает заявка, сохраняя снимок конфигурации (тикет 21).

Метод — GET: расчёт ничего не меняет, и повторить его можно сколько
угодно раз. CSRF ему поэтому не нужен, в отличие от приёма заявки.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

import pydantic
from dmr import Controller, Query, modify
from dmr.plugins.pydantic import PydanticSerializer

from memiro.api.errors import UNPROCESSABLE, reject
from memiro.api.ids import IDS_PATTERN, MAX_IDS_LENGTH, parse_ids
from . import quoting


class PriceQuery(pydantic.BaseModel):
    """Что считать: товар, габариты и выбранные покупателем значения."""

    product: Annotated[int, pydantic.Field(ge=1)]
    width_mm: quoting.Side
    height_mm: quoting.Side
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


class PriceController(Controller[PydanticSerializer]):
    """Цена конфигурации: считается на сервере, тарифы наружу не идут."""

    @modify(extra_responses=[UNPROCESSABLE])
    def get(self, parsed_query: Query[PriceQuery]) -> PriceQuote:
        try:
            quote = quoting.quote(
                product_id=parsed_query.product,
                width_mm=parsed_query.width_mm,
                height_mm=parsed_query.height_mm,
                value_ids=parse_ids(parsed_query.values),
            )
        except quoting.UncalculableError as refusal:
            reject(self, str(refusal))
        if not quote.fits():
            return PriceQuote(total=None, additions=[], needs_inquiry=True)
        total = quote.total
        if total is None:
            # Размер подошёл, а платных статей не осталось: выбор
            # покупателя обнулил единственную (тикет 19)
            reject(self, quoting.UNCALCULABLE)
        return PriceQuote(
            total=total,
            additions=_additions(quote),
            needs_inquiry=False,
        )


def _additions(quote: quoting.Quote) -> list[PriceAddition]:
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
    full = quote.cost(quote.chosen)
    additions = []
    for value in quote.chosen:
        rest = [other for other in quote.chosen if other.pk != value.pk]
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
