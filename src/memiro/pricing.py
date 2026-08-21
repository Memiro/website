"""Движок цены: размеры и тарифы выбранных значений → итог (ADR-0007).

Django сюда не импортируется. Тарифы приходят аргументом готовой
структурой, поэтому движок тестируется таблицей без базы, а сборка
справочника живёт снаружи и в одном месте.

Наружу торчит одна роль — `PriceEngine`; `calculate_price` — её
реализация по ADR-0007. Заменить формулу — значит подставить другую
функцию того же протокола, не трогая тех, кто её зовёт.

Разложение отдаётся строкой на каждую платную статью. Что из него
показать покупателю, решает вызывающий: ставки за метр, коэффициенты и
разбор на стекло с кромкой в браузер не уезжают.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Protocol, runtime_checkable

MM_PER_M = Decimal(1000)
MM2_PER_M2 = Decimal(1_000_000)
# Копейки живут в разложении; итог округляется до сотни рублей
KOPECK = Decimal("0.01")
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
class Tariff:
    """Строка тарифа выбранного значения атрибута.

    Пустая единица со ставкой `None` — «бесплатно»: значение описывает
    изделие, но денег не стоит (холодный свет, цвет рамы).
    """

    label: str
    unit: Unit | None = None
    rate: Decimal | None = None
    # Сколько раз статья входит в изделие: два выреза — два тарифа
    quantity: int = 1
    # Коэффициент формы умножает то, что режется по контуру, — стекло и
    # кромку. Лента на криволинейном резе дороже не становится
    scaled_by_shape: bool = False


@dataclass(frozen=True, slots=True)
class Configuration:
    """Что считаем: габариты изделия и тарифы всего, что в нём выбрано."""

    width_mm: int
    height_mm: int
    tariffs: tuple[Tariff, ...] = ()


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


@runtime_checkable
class PriceEngine(Protocol):
    """Роль движка: конфигурация и пороги → цена."""

    def __call__(
        self,
        configuration: Configuration,
        *,
        min_area_m2: Decimal = ...,
        min_order_total: int = ...,
    ) -> Price: ...


def calculate_price(
    configuration: Configuration,
    *,
    min_area_m2: Decimal = Decimal(0),
    min_order_total: int = 0,
) -> Price:
    """Цена конфигурации по единицам расхода (ADR-0007).

    Пороги по умолчанию нулевые — это «без порога», а не значения
    владельца: настоящие живут в админке (`PricingSettings`).
    """
    area_m2 = max(_area_m2(configuration), min_area_m2)
    perimeter_m = _perimeter_m(configuration)
    shape_factor = _shape_factor(configuration.tariffs)
    lines = tuple(
        PriceLine(label=tariff.label, amount=amount)
        for tariff in configuration.tariffs
        if (
            amount := _amount(
                tariff,
                area_m2=area_m2,
                perimeter_m=perimeter_m,
                shape_factor=shape_factor,
            )
        )
        is not None
    )
    total = max(
        sum((line.amount for line in lines), Decimal(0)),
        Decimal(min_order_total),
    )
    return Price(total=_round_up(total), lines=lines)


def _area_m2(configuration: Configuration) -> Decimal:
    _check_size(configuration)
    return (
        Decimal(configuration.width_mm * configuration.height_mm) / MM2_PER_M2
    )


def _perimeter_m(configuration: Configuration) -> Decimal:
    _check_size(configuration)
    return (
        Decimal(2 * (configuration.width_mm + configuration.height_mm))
        / MM_PER_M
    )


def _check_size(configuration: Configuration) -> None:
    if configuration.width_mm > 0 and configuration.height_mm > 0:
        return
    message = "Нужен положительный размер изделия в миллиметрах."
    raise ValueError(message)


def _shape_factor(tariffs: tuple[Tariff, ...]) -> Decimal:
    """Коэффициенты формы перемножаются; их отсутствие — единица."""
    factor = Decimal(1)
    for tariff in tariffs:
        if tariff.unit is Unit.FACTOR and tariff.rate is not None:
            factor *= tariff.rate
    return factor


def _amount(
    tariff: Tariff,
    *,
    area_m2: Decimal,
    perimeter_m: Decimal,
    shape_factor: Decimal,
) -> Decimal | None:
    """Сколько стоит статья — или ничего, если она не платная.

    Коэффициент формы своей строкой в итог не входит: он уже сидит
    множителем в стекле и кромке.
    """
    if tariff.rate is None or tariff.unit is None:
        return None
    consumed = {
        Unit.PIECE: Decimal(1),
        Unit.LINEAR_METER: perimeter_m,
        Unit.SQUARE_METER: area_m2,
        Unit.FACTOR: None,
    }[tariff.unit]
    if consumed is None:
        return None
    amount = tariff.rate * consumed * tariff.quantity
    if tariff.scaled_by_shape:
        amount *= shape_factor
    return amount.quantize(KOPECK, rounding=ROUND_HALF_UP)


def _round_up(total: Decimal) -> int:
    """Вверх до сотни рублей: покупателю называют круглое число."""
    steps = (total / ROUNDING_STEP).to_integral_value(rounding=ROUND_CEILING)
    return int(steps * ROUNDING_STEP)
