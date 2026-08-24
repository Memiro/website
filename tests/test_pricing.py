"""Табличные тесты движка цены — без базы (ADR-0007, тикет 16).

Тарифы в примерах — условные из ADR-0007: полотно 4 000 ₽/м², кромка
700 ₽/пог. м, контурная подсветка 2 500 ₽/пог. м, выключатель 1 500 ₽.
"""

from decimal import Decimal

import pytest

from memiro.pricing import (
    Configuration,
    Price,
    PriceEngine,
    PriceLine,
    PricingLimits,
    SelectedValue,
    Unit,
    calculate_price,
)

# Ожидаемые числа отдельных тестов: у таблицы они приходят параметром
ROUNDED_TOTAL = 8400
SQUARE_METRE_OF_GLASS = 4000
FLAT_RATE = 9900

NO_LIMITS = PricingLimits()
MIN_AREA = PricingLimits(min_area_m2=Decimal("0.25"))
MIN_ORDER = PricingLimits(min_area_m2=Decimal("0.25"), min_order_total=15000)

# Полотно и кромка режутся по контуру — их и умножает коэффициент формы
GLASS = SelectedValue(
    label="Полотно",
    unit=Unit.SQUARE_METER,
    rate=Decimal(4000),
    scaled_by_shape=True,
)
EDGE = SelectedValue(
    label="Обработка кромки",
    unit=Unit.LINEAR_METER,
    rate=Decimal(700),
    scaled_by_shape=True,
)
CONTOUR = SelectedValue(
    label="Контурная подсветка",
    unit=Unit.LINEAR_METER,
    rate=Decimal(2500),
)
FRONTAL = SelectedValue(
    label="Фронтальная подсветка",
    unit=Unit.SQUARE_METER,
    rate=Decimal(1200),
)
SWITCH = SelectedValue(
    label="Выключатель", unit=Unit.PIECE, rate=Decimal(1500)
)
HEATING = SelectedValue(label="Подогрев", unit=Unit.PIECE, rate=Decimal(3500))
THREE_IN_ONE = SelectedValue(label="3 в 1", unit=Unit.PIECE, rate=Decimal(900))
CUTOUTS = SelectedValue(
    label="Вырез", unit=Unit.PIECE, rate=Decimal(500), quantity=Decimal(2)
)
ROUND_SHAPE = SelectedValue(
    label="Круглое", unit=Unit.FACTOR, rate=Decimal("1.5")
)
# Значение справочника без тарифа: описывает изделие, но денег не стоит
COLD_LIGHT = SelectedValue(label="Холодный свет")


def charged(price: Price) -> Decimal:
    """Сумма статей до округления итога."""
    return sum((line.amount for line in price.lines), Decimal(0))


@pytest.mark.parametrize(
    ("configuration", "limits", "expected"),
    [
        pytest.param(
            Configuration(1900, 400, (GLASS, EDGE)),
            NO_LIMITS,
            6300,
            id="напольное 0,76 м² — 4,60 пог. м кромки",
        ),
        pytest.param(
            Configuration(870, 870, (GLASS, EDGE)),
            NO_LIMITS,
            5500,
            id="квадратное 0,76 м² — 3,48 пог. м кромки",
        ),
        pytest.param(
            Configuration(870, 870, (GLASS, EDGE, CONTOUR, SWITCH)),
            NO_LIMITS,
            15700,
            id="прямой рез",
        ),
        pytest.param(
            Configuration(
                870, 870, (GLASS, EDGE, CONTOUR, SWITCH, ROUND_SHAPE)
            ),
            NO_LIMITS,
            18400,
            id="криволинейный рез — плюс половина стекла с кромкой",
        ),
        pytest.param(
            Configuration(400, 400, (GLASS,)),
            NO_LIMITS,
            700,
            id="без порога площади считается 0,16 м²",
        ),
        pytest.param(
            Configuration(400, 400, (GLASS,)),
            MIN_AREA,
            1000,
            id="маленькое зеркало считается по минимальной площади",
        ),
        pytest.param(
            Configuration(400, 400, (GLASS,)),
            MIN_ORDER,
            15000,
            id="итог поднят до минимальной суммы заказа",
        ),
        pytest.param(
            Configuration(500, 500, (GLASS,)),
            NO_LIMITS,
            1000,
            id="кратный сотне итог округление не трогает",
        ),
        pytest.param(
            Configuration(
                500,
                500,
                (
                    SelectedValue(
                        label="Полотно",
                        unit=Unit.SQUARE_METER,
                        rate=Decimal(4001),
                    ),
                ),
            ),
            NO_LIMITS,
            1100,
            id="1 000,25 ₽ — вверх до сотни, а не к ближайшей",
        ),
        pytest.param(
            Configuration(1000, 1000, (GLASS, COLD_LIGHT)),
            NO_LIMITS,
            4000,
            id="значение без тарифа бесплатно",
        ),
        pytest.param(
            Configuration(1000, 1000, (GLASS, THREE_IN_ONE)),
            NO_LIMITS,
            4900,
            id="температура стоит денег только у «3 в 1»",
        ),
        pytest.param(
            Configuration(1000, 1000, (GLASS, CONTOUR, HEATING)),
            NO_LIMITS,
            17500,
            id="не выбранная кнопка не оплачивается",
        ),
        pytest.param(
            Configuration(1000, 1000, (GLASS, CONTOUR, HEATING, SWITCH)),
            NO_LIMITS,
            19000,
            id="выбранная кнопка оплачивается",
        ),
        pytest.param(
            Configuration(1000, 1000, (CUTOUTS,)),
            NO_LIMITS,
            1000,
            id="два выреза стоят вдвое",
        ),
    ],
)
def test_price_of_a_configuration(
    configuration: Configuration,
    limits: PricingLimits,
    expected: int,
) -> None:
    priced = calculate_price(configuration, limits=limits)

    assert priced.total == expected


def test_shape_factor_spares_illumination_and_pieces() -> None:
    """Коэффициент формы умножает стекло и кромку — и только их."""
    values = (GLASS, EDGE, CONTOUR, SWITCH)
    straight = calculate_price(Configuration(870, 870, values))
    curved = calculate_price(Configuration(870, 870, (*values, ROUND_SHAPE)))

    untouched = {CONTOUR.label, SWITCH.label}
    assert [line for line in curved.lines if line.label in untouched] == [
        line for line in straight.lines if line.label in untouched
    ]


def test_combined_illumination_is_contour_plus_frontal() -> None:
    """Комбинированная — обе строки сразу, без собственного тарифа.

    Сравниваются статьи, а не итоги: округление вверх до сотни трижды
    сделало бы равенство случайным.
    """
    contour = calculate_price(Configuration(1370, 940, (CONTOUR,)))
    frontal = calculate_price(Configuration(1370, 940, (FRONTAL,)))
    combined = calculate_price(Configuration(1370, 940, (CONTOUR, FRONTAL)))

    assert charged(combined) == charged(contour) + charged(frontal)


def test_lines_are_exact_and_only_the_total_is_rounded() -> None:
    """ADR округляет итог, а не статьи: копейки складываются как есть."""
    priced = calculate_price(Configuration(1370, 940, (GLASS, EDGE)))

    assert charged(priced) == Decimal("8385.20")
    assert priced.total == ROUNDED_TOTAL


def test_breakdown_labels_every_charged_line() -> None:
    """Разложение — сырьё для подписей эндпоинта.

    Бестарифное значение и коэффициент формы своей строки не дают:
    коэффициент уже сидит множителем в стекле.
    """
    priced = calculate_price(
        Configuration(1000, 1000, (GLASS, CONTOUR, COLD_LIGHT, ROUND_SHAPE))
    )

    assert priced.lines == (
        PriceLine(label="Полотно", amount=Decimal(6000)),
        PriceLine(label="Контурная подсветка", amount=Decimal(10000)),
    )


@pytest.mark.parametrize(("width", "height"), [(0, 600), (600, 0), (-1, 600)])
def test_a_mirror_without_size_is_not_a_price(width: int, height: int) -> None:
    with pytest.raises(ValueError, match="размер"):
        Configuration(width, height, (GLASS,))


def test_the_engine_is_replaceable() -> None:
    """Формула подменяема: вызывающий зовёт роль, а не реализацию.

    Подпись держит mypy — обе функции присвоены переменной роли;
    вызов показывает, что вызывающему хватает протокола.
    """

    def flat_rate(
        configuration: Configuration,
        *,
        limits: PricingLimits = NO_LIMITS,
    ) -> Price:
        return Price(total=FLAT_RATE, lines=())

    canonical: PriceEngine = calculate_price
    replacement: PriceEngine = flat_rate
    square = Configuration(1000, 1000, (GLASS,))

    assert canonical(square).total == SQUARE_METRE_OF_GLASS
    assert replacement(square).total == FLAT_RATE


LIMITED = PricingLimits(max_long_side_mm=2000, max_short_side_mm=1500)


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (2000, 1500, True),
        (1500, 2000, True),
        (2001, 1500, False),
        (400, 1900, True),
        (1900, 1600, False),
    ],
)
def test_production_limits_are_read_side_by_side(
    width: int, height: int, *, expected: bool
) -> None:
    """Изделие поворачивают: пределы сверяются длинной и короткой стороной."""
    assert LIMITED.fits(width_mm=width, height_mm=height) is expected


def test_without_limits_no_size_is_out_of_range() -> None:
    """Нулевой предел — его отсутствие, а не запрет любого размера."""
    assert NO_LIMITS.fits(width_mm=9000, height_mm=9000)
