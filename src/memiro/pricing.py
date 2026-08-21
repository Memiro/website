"""Движок цены: размеры и выбранные значения → итог (ADR-0007).

Django сюда не импортируется. Значения приходят аргументом готовой
структурой, поэтому движок тестируется таблицей без базы, а сборка
справочника живёт снаружи и в одном месте.

Наружу торчит одна роль — `PriceEngine`; `calculate_price` — её
реализация по ADR-0007. Заменить формулу — значит подставить другую
функцию того же протокола, не трогая тех, кто её зовёт.

Разложение отдаётся строкой на каждую платную статью — из него
эндпоинт собирает подписи выбранных добавок. Что показать покупателю,
решает вызывающий: ставки за метр, коэффициенты и разбор на стекло с
кромкой в браузер не уезжают.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from typing import Protocol

MM_PER_M = Decimal(1000)
MM2_PER_M2 = Decimal(1_000_000)
# Итог округляется до сотни рублей; статьи разложения — точные
ROUNDING_STEP = Decimal(100)


class Unit(StrEnum):
    """Единица, в которой значение атрибута расходуется.

    Канон: справочник атрибутов (`AttributeValue.Unit`) берёт значения
    отсюда, чтобы админка и движок не разошлись.
    """

    PIECE = "piece"
    LINEAR_METER = "linear_meter"
    SQUARE_METER = "square_meter"
    FACTOR = "factor"


@dataclass(frozen=True, slots=True)
class SelectedValue:
    """Выбранное значение атрибута со своим тарифом.

    Пустая единица со ставкой `None` — «бесплатно»: значение описывает
    изделие, но денег не стоит (холодный свет, цвет рамы).
    """

    label: str
    unit: Unit | None = None
    rate: Decimal | None = None
    # Числовой атрибут говорит, сколько раз статья входит в изделие:
    # два выреза стоят вдвое (тикет 22, «Вырез: количество»)
    quantity: int = 1
    # Коэффициент формы умножает то, что режется по контуру, — стекло и
    # кромку. Лента на криволинейном резе дороже не становится, хотя
    # меряется тем же погонным метром, что и кромка
    scaled_by_shape: bool = False

    def amount(
        self,
        *,
        area_m2: Decimal,
        perimeter_m: Decimal,
        shape_factor: Decimal,
    ) -> Decimal | None:
        """Сколько стоит статья — или ничего, если значение бесплатное.

        Коэффициенты сюда не доходят: их отбирают до расчёта статей.
        """
        if self.rate is None or self.unit is None:
            return None
        consumed = {
            Unit.PIECE: Decimal(1),
            Unit.LINEAR_METER: perimeter_m,
            Unit.SQUARE_METER: area_m2,
        }[self.unit]
        amount = self.rate * consumed * self.quantity
        return amount * shape_factor if self.scaled_by_shape else amount


@dataclass(frozen=True, slots=True)
class Configuration:
    """Что считаем: габариты изделия и всё, что в нём выбрано."""

    width_mm: int
    height_mm: int
    values: tuple[SelectedValue, ...] = ()

    def __post_init__(self) -> None:
        """Нулевой и отрицательный габарит — не дешёвое зеркало, а ошибка."""
        if self.width_mm > 0 and self.height_mm > 0:
            return
        message = "Нужен положительный размер изделия в миллиметрах."
        raise ValueError(message)

    @property
    def area_m2(self) -> Decimal:
        return Decimal(self.width_mm * self.height_mm) / MM2_PER_M2

    @property
    def perimeter_m(self) -> Decimal:
        return Decimal(2 * (self.width_mm + self.height_mm)) / MM_PER_M


@dataclass(frozen=True, slots=True)
class PricingThresholds:
    """Пороги расчёта — «Параметры расчёта» админки глазами движка.

    Нули по умолчанию означают «без порога», а не цифры владельца: его
    живут строкой `catalog.PricingSettings` и приезжают сборкой.
    """

    min_area_m2: Decimal = field(default_factory=lambda: Decimal(0))
    min_order_total: int = 0


NO_THRESHOLDS = PricingThresholds()


@dataclass(frozen=True, slots=True)
class PriceLine:
    """Платная статья итога: за что и сколько."""

    label: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class Price:
    """Итог в рублях и статьи, из которых он сложился."""

    total: int
    lines: tuple[PriceLine, ...]


class PriceEngine(Protocol):
    """Роль движка: конфигурация и пороги → цена."""

    def __call__(
        self,
        configuration: Configuration,
        *,
        thresholds: PricingThresholds = ...,
    ) -> Price: ...


def calculate_price(
    configuration: Configuration,
    *,
    thresholds: PricingThresholds = NO_THRESHOLDS,
) -> Price:
    """Цена конфигурации по единицам расхода (ADR-0007)."""
    area_m2 = max(configuration.area_m2, thresholds.min_area_m2)
    shape_factor, charged = _split_off_shape_factors(configuration.values)
    lines = tuple(
        PriceLine(label=value.label, amount=amount)
        for value in charged
        if (
            amount := value.amount(
                area_m2=area_m2,
                perimeter_m=configuration.perimeter_m,
                shape_factor=shape_factor,
            )
        )
        is not None
    )
    total = max(
        sum((line.amount for line in lines), Decimal(0)),
        Decimal(thresholds.min_order_total),
    )
    return Price(total=_round_up(total), lines=lines)


def _split_off_shape_factors(
    values: tuple[SelectedValue, ...],
) -> tuple[Decimal, tuple[SelectedValue, ...]]:
    """Отделяет коэффициенты от расходуемых статей.

    Коэффициент своей строкой в итог не входит — он множитель у того,
    что режется по контуру. Несколько коэффициентов перемножаются,
    отсутствие — единица.
    """
    factor = Decimal(1)
    charged: list[SelectedValue] = []
    for value in values:
        if value.unit is not Unit.FACTOR:
            charged.append(value)
        elif value.rate is not None:
            factor *= value.rate
    return factor, tuple(charged)


def _round_up(total: Decimal) -> int:
    """Вверх до сотни рублей: покупателю называют круглое число."""
    steps = (total / ROUNDING_STEP).to_integral_value(rounding=ROUND_CEILING)
    return int(steps * ROUNDING_STEP)
