"""Табличные тесты движка цены — без базы (ADR-0007, тикет 16).

Тарифы в примерах — условные из ADR-0007: полотно 4 000 ₽/м², кромка
700 ₽/пог. м, контурная подсветка 2 500 ₽/пог. м, выключатель 1 500 ₽.
"""

from decimal import Decimal

import pytest

from memiro.pricing import (
    Configuration,
    PriceEngine,
    PriceLine,
    Tariff,
    Unit,
    calculate_price,
)


def money(value: str | int) -> Decimal:
    return Decimal(value)


NO_MINIMUM = money(0)
MIN_AREA = money("0.25")

# Полотно и кромка режутся по контуру — их и умножает коэффициент формы
GLASS = Tariff(
    label="Полотно",
    unit=Unit.SQUARE_METER,
    rate=money(4000),
    scaled_by_shape=True,
)
EDGE = Tariff(
    label="Обработка кромки",
    unit=Unit.LINEAR_METER,
    rate=money(700),
    scaled_by_shape=True,
)
CONTOUR = Tariff(
    label="Контурная подсветка",
    unit=Unit.LINEAR_METER,
    rate=money(2500),
)
FRONTAL = Tariff(
    label="Фронтальная подсветка",
    unit=Unit.SQUARE_METER,
    rate=money(1200),
)
SWITCH = Tariff(label="Выключатель", unit=Unit.PIECE, rate=money(1500))
HEATING = Tariff(label="Подогрев", unit=Unit.PIECE, rate=money(3500))
THREE_IN_ONE = Tariff(label="3 в 1", unit=Unit.PIECE, rate=money(900))
CUTOUTS = Tariff(label="Вырез", unit=Unit.PIECE, rate=money(500), quantity=2)
ROUND_SHAPE = Tariff(label="Круглое", unit=Unit.FACTOR, rate=money("1.5"))
# Значение справочника без тарифа: описывает изделие, но денег не стоит
COLD_LIGHT = Tariff(label="Холодный свет")


@pytest.mark.parametrize(
    ("configuration", "min_area_m2", "min_order_total", "expected"),
    [
        pytest.param(
            Configuration(1900, 400, (GLASS, EDGE)),
            NO_MINIMUM,
            0,
            6300,
            id="напольное 0,76 м² — 4,60 пог. м кромки",
        ),
        pytest.param(
            Configuration(870, 870, (GLASS, EDGE)),
            NO_MINIMUM,
            0,
            5500,
            id="квадратное 0,76 м² — 3,48 пог. м кромки",
        ),
        pytest.param(
            Configuration(870, 870, (GLASS, EDGE, CONTOUR, SWITCH)),
            NO_MINIMUM,
            0,
            15700,
            id="прямой рез",
        ),
        pytest.param(
            Configuration(
                870, 870, (GLASS, EDGE, CONTOUR, SWITCH, ROUND_SHAPE)
            ),
            NO_MINIMUM,
            0,
            18400,
            id="криволинейный рез — плюс половина стекла с кромкой",
        ),
        pytest.param(
            Configuration(400, 400, (GLASS,)),
            NO_MINIMUM,
            0,
            700,
            id="без порога площади считается 0,16 м²",
        ),
        pytest.param(
            Configuration(400, 400, (GLASS,)),
            MIN_AREA,
            0,
            1000,
            id="маленькое зеркало считается по минимальной площади",
        ),
        pytest.param(
            Configuration(400, 400, (GLASS,)),
            MIN_AREA,
            15000,
            15000,
            id="итог поднят до минимальной суммы заказа",
        ),
        pytest.param(
            Configuration(500, 500, (GLASS,)),
            NO_MINIMUM,
            0,
            1000,
            id="кратный сотне итог округление не трогает",
        ),
        pytest.param(
            Configuration(
                500,
                500,
                (
                    Tariff(
                        label="Полотно",
                        unit=Unit.SQUARE_METER,
                        rate=money(4001),
                    ),
                ),
            ),
            NO_MINIMUM,
            0,
            1100,
            id="1 000,25 ₽ — вверх до сотни, а не к ближайшей",
        ),
        pytest.param(
            Configuration(1000, 1000, (GLASS, COLD_LIGHT)),
            NO_MINIMUM,
            0,
            4000,
            id="значение без тарифа бесплатно",
        ),
        pytest.param(
            Configuration(1000, 1000, (GLASS, THREE_IN_ONE)),
            NO_MINIMUM,
            0,
            4900,
            id="температура стоит денег только у «3 в 1»",
        ),
        pytest.param(
            Configuration(1000, 1000, (GLASS, CONTOUR, HEATING)),
            NO_MINIMUM,
            0,
            17500,
            id="не выбранная кнопка не оплачивается",
        ),
        pytest.param(
            Configuration(1000, 1000, (GLASS, CONTOUR, HEATING, SWITCH)),
            NO_MINIMUM,
            0,
            19000,
            id="выбранная кнопка оплачивается",
        ),
        pytest.param(
            Configuration(1000, 1000, (CUTOUTS,)),
            NO_MINIMUM,
            0,
            1000,
            id="два выреза стоят вдвое",
        ),
    ],
)
def test_price_of_a_configuration(
    configuration: Configuration,
    min_area_m2: Decimal,
    min_order_total: int,
    expected: int,
) -> None:
    priced = calculate_price(
        configuration,
        min_area_m2=min_area_m2,
        min_order_total=min_order_total,
    )

    assert priced.total == expected


def test_shape_factor_spares_illumination_and_pieces() -> None:
    """Коэффициент формы умножает стекло и кромку — и только их."""
    tariffs = (GLASS, EDGE, CONTOUR, SWITCH)
    straight = calculate_price(Configuration(870, 870, tariffs))
    curved = calculate_price(Configuration(870, 870, (*tariffs, ROUND_SHAPE)))

    untouched = {CONTOUR.label, SWITCH.label}
    assert [line for line in curved.lines if line.label in untouched] == [
        line for line in straight.lines if line.label in untouched
    ]


def test_combined_illumination_is_contour_plus_frontal() -> None:
    """Комбинированная — обе строки сразу, без собственного тарифа."""
    contour = calculate_price(Configuration(1000, 1000, (CONTOUR,)))
    frontal = calculate_price(Configuration(1000, 1000, (FRONTAL,)))
    combined = calculate_price(Configuration(1000, 1000, (CONTOUR, FRONTAL)))

    assert combined.total == contour.total + frontal.total


def test_breakdown_labels_every_charged_line() -> None:
    """Разложение — сырьё для подписей эндпоинта.

    Бестарифное значение и коэффициент формы своей строки не дают:
    коэффициент уже сидит множителем в стекле.
    """
    priced = calculate_price(
        Configuration(1000, 1000, (GLASS, CONTOUR, COLD_LIGHT, ROUND_SHAPE))
    )

    assert priced.lines == (
        PriceLine(label="Полотно", amount=money(6000)),
        PriceLine(label="Контурная подсветка", amount=money(10000)),
    )


@pytest.mark.parametrize(("width", "height"), [(0, 600), (600, 0), (-1, 600)])
def test_a_mirror_without_size_is_not_a_price(width: int, height: int) -> None:
    with pytest.raises(ValueError, match="размер"):
        calculate_price(Configuration(width, height, (GLASS,)))


def test_the_engine_is_replaceable() -> None:
    """Формула подменяема: витрина зовёт роль, а не реализацию."""
    assert isinstance(calculate_price, PriceEngine)
