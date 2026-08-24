"""Демонстрационные тарифы, разметка и варианты — чтобы витрину было видно.

**Цифры здесь выдуманы.** Скрипт заполняет локальную базу тем, чего
ждёт владелец: ставками в справочнике, параметрами расчёта, недостающей
разметкой товаров и предпосчитанными вариантами. Без них каталог молчит
о цене (тикет 18), а карточка не показывает калькулятор (тикет 20) —
смотреть на витрину не на чем.

`remap.py` тарифы ставить отказался намеренно: выдуманная ставка
однажды назвала бы покупателю неверную цену. Здесь она называет её
осознанно и только на машине разработчика — ради того, чтобы увидеть,
как страница выглядит с числами. На боевую базу это не едет: прогон
отказывается работать там, где задан `POSTGRES_HOST`.

Запуск из корня репозитория:

    uv run python .scratch/new-site/demo/seed_pricing.py
    uv run python .scratch/new-site/demo/seed_pricing.py --undo

Повторный прогон ничего не портит и не удваивает: тариф доводится до
той же ставки, разметка ставится только там, где её нет, варианты
сверяются по размеру. Отчёт прогона ложится рядом в `seeded.json` —
по нему `--undo` снимает ровно то, что поставил прогон, не трогая
того, что вы успели завести руками.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import django
from django.apps import apps

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

if not apps.ready:
    sys.path.insert(0, str(REPO / "src"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memiro.settings")
    django.setup()

from django.db import transaction  # noqa: E402

from memiro.catalog import calculator, repricing, tariffs  # noqa: E402
from memiro.catalog.models import (  # noqa: E402
    Attribute,
    AttributeValue,
    PricingSettings,
    Product,
    ProductAttribute,
    ProductVariant,
    marks_presence,
)

CATEGORY_SLUG = "zerkala"
LEDGER = HERE / "seeded.json"

PIECE = AttributeValue.Unit.PIECE
LINEAR = AttributeValue.Unit.LINEAR_METER
SQUARE = AttributeValue.Unit.SQUARE_METER
FACTOR = AttributeValue.Unit.FACTOR

# Ставки взяты с потолка: порядок величин правдоподобен, сами числа —
# нет. Пустая единица со ставкой None означает «бесплатно» — так
# заведены значения, которые описывают изделие, но денег не стоят
TARIFFS: dict[str, dict[str, tuple[str, str] | None]] = {
    "Тип полотна": {
        "Серебро": (SQUARE, "4500"),
        "Осветлённое": (SQUARE, "6200"),
        "Бронза": (SQUARE, "7000"),
        "Графит": (SQUARE, "7000"),
    },
    "Форма": {
        "Прямоугольное": (FACTOR, "1.0"),
        "Круглое": (FACTOR, "1.5"),
        "Фигурное": (FACTOR, "1.8"),
    },
    "Рама": {
        "Алюминий": (LINEAR, "2200"),
        "Багет": (LINEAR, "3500"),
        "Без рамы": None,
    },
    "Цвет рамы": dict.fromkeys(
        ("Чёрный", "Белый", "Золото", "Серебро", "Бронза", "Голубой", "Другое")
    ),
    # Подсветка вся меряется погонным метром, с какой бы стороны
    # полотна ни шла лента; разнятся ставки, а не единица.
    # Комбинированная — сумма двух: 2500 + 3200
    "Подсветка": {
        "Контурная": (LINEAR, "2500"),
        "Фронтальная": (LINEAR, "3200"),
        "Комбинированная": (LINEAR, "5700"),
        "Без подсветки": None,
    },
    "Температура свечения": {
        "Холодная": None,
        "Тёплая": None,
        "Нейтральная": None,
        "3 в 1": (PIECE, "1500"),
    },
    "Кнопка": {
        "Механическая": (PIECE, "800"),
        "Сенсорная": (PIECE, "1500"),
        "Датчик на взмах": (PIECE, "2500"),
        "Без кнопки": None,
    },
    "Крепление": {
        "С креплением": (PIECE, "500"),
        "На ножке": (PIECE, "3500"),
        "Без крепления": None,
    },
    "Подогрев": {
        "С подогревом": (PIECE, "3500"),
        "Без подогрева": None,
    },
    "Вырез": {"Вырез": (PIECE, "1200")},
}

# Полотно и рама режутся по контуру — на криволинейном резе дороже.
# Лента меряется тем же погонным метром, но коэффициентом формы не
# умножается (CONTEXT.md, «Атрибут»)
SCALED_BY_SHAPE = {
    ("Тип полотна", None),
    ("Рама", "Алюминий"),
    ("Рама", "Багет"),
}

SETTINGS = {
    "min_area_m2": Decimal("0.250"),
    "min_order_total": 2000,
    "max_long_side_mm": 2400,
    "max_short_side_mm": 1500,
}


# Чем заполняются пробелы разметки. Первое совпавшее слово выигрывает;
# не совпало ничего — берётся последнее значение, `fallback`
@dataclass(frozen=True, slots=True)
class Guess:
    """Как демо-прогон угадывает значение по названию и описанию."""

    attribute: str
    by_word: tuple[tuple[str, str], ...]
    fallback: str


# Порядок значим: родитель заводится раньше ребёнка, иначе ребёнок
# будет пропущен как сирота. Кнопка живёт при подсветке или подогреве,
# и потому идёт после обоих
GUESSES = (
    Guess(
        "Тип полотна",
        (("графит", "Графит"), ("бронз", "Бронза"), ("осветл", "Осветлённое")),
        "Серебро",
    ),
    Guess(
        "Рама",
        (("багет", "Багет"), ("алюмини", "Алюминий"), ("в раме", "Алюминий")),
        "Без рамы",
    ),
    Guess("Цвет рамы", (), "Другое"),
    Guess(
        "Подсветка",
        (
            ("комбинирован", "Комбинированная"),
            ("фронтальн", "Фронтальная"),
            ("контурн", "Контурная"),
            ("подсветк", "Контурная"),
            ("led", "Контурная"),
        ),
        "Без подсветки",
    ),
    Guess("Температура свечения", (), "Нейтральная"),
    Guess("Подогрев", (("подогрев", "С подогревом"),), "Без подогрева"),
    Guess("Кнопка", (("сенсорн", "Сенсорная"),), "Сенсорная"),
    Guess(
        "Крепление",
        (("напольн", "На ножке"), ("на ножке", "На ножке")),
        "С креплением",
    ),
)

# Три типовых размера на товар — таблица вариантов карточки и источник
# «цены от» в каталоге. Значений своих у них нет: вариант берёт
# умолчания товара, и калькулятор открывается на первом из них
VARIANT_SIZES = ((600, 800), (800, 1000), (1000, 1400))


@dataclass
class Ledger:
    """Что прогон завёл — чтобы `--undo` снял ровно это."""

    values: dict[str, list[object]]
    rows: list[int]
    variants: list[int]
    settings_created: bool

    @classmethod
    def empty(cls) -> Ledger:
        return cls(values={}, rows=[], variants=[], settings_created=False)

    @classmethod
    def load(cls) -> Ledger | None:
        if not LEDGER.exists():
            return None
        return cls(**json.loads(LEDGER.read_text(encoding="utf-8")))

    def save(self) -> None:
        LEDGER.write_text(
            json.dumps(self.__dict__, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def seed_tariffs(ledger: Ledger) -> list[str]:
    """Ставит ставки значениям справочника, запоминая прежние."""
    report: list[str] = []
    for attribute_name, rows in TARIFFS.items():
        attribute = Attribute.objects.filter(
            category__slug=CATEGORY_SLUG, name=attribute_name
        ).first()
        if attribute is None:
            report.append(f"  ! атрибута «{attribute_name}» нет — пропущен")
            continue
        for value_name, tariff in rows.items():
            value = attribute.values.filter(value=value_name).first()
            if value is None:
                report.append(
                    f"  ! значения «{attribute_name}: {value_name}» нет"
                )
                continue
            unit, rate = tariff or ("", None)
            scaled = (attribute_name, None) in SCALED_BY_SHAPE or (
                attribute_name,
                value_name,
            ) in SCALED_BY_SHAPE
            key = str(value.pk)
            if key not in ledger.values:
                ledger.values[key] = [
                    value.unit,
                    str(value.rate) if value.rate is not None else None,
                    value.scaled_by_shape,
                ]
            value.unit = unit
            value.rate = Decimal(rate) if rate is not None else None
            value.scaled_by_shape = scaled
            value.save(update_fields=("unit", "rate", "scaled_by_shape"))
    report.append(f"  тарифов проставлено: {len(ledger.values)}")
    return report


def seed_settings(ledger: Ledger) -> list[str]:
    """Заводит параметры расчёта, если их ещё нет."""
    existing = PricingSettings.objects.first()
    if existing is not None and not ledger.settings_created:
        return ["  параметры расчёта уже заведены — не тронуты"]
    PricingSettings.objects.update_or_create(
        pk=PricingSettings.SINGLETON_PK, defaults=SETTINGS
    )
    ledger.settings_created = True
    return [
        "  параметры расчёта заведены: "
        f"мин. площадь {SETTINGS['min_area_m2']} м², "
        f"мин. сумма {SETTINGS['min_order_total']} ₽, "
        f"предел {SETTINGS['max_long_side_mm']}×"
        f"{SETTINGS['max_short_side_mm']} мм"
    ]


def _haystack(product: Product) -> str:
    return f"{product.name} {product.description}".lower()


def seed_markup(ledger: Ledger) -> list[str]:
    """Заполняет пробелы разметки — только там, где значения нет.

    Зависимый атрибут заводится лишь при живом родителе: температуры
    свечения не бывает у зеркала без подсветки, и строка «Нейтральная»
    у такого товара — не пробел, а неправда. Модель этого не стережёт:
    проверка сироты живёт в форме товара, а скрипт пишет мимо форм —
    ровно то ограничение, о котором предупреждает тикет 15.
    """
    dictionary = {
        attribute.name: attribute
        for attribute in Attribute.objects.filter(
            category__slug=CATEGORY_SLUG
        ).prefetch_related("values", "parents")
    }
    filled = 0
    orphaned = 0
    for product in Product.objects.filter(
        category__slug=CATEGORY_SLUG
    ).prefetch_related("attribute_values__value_option"):
        rows = list(product.attribute_values.all())
        taken = {row.attribute_id for row in rows}
        present = {
            row.attribute_id
            for row in rows
            if marks_presence(
                value_bool=row.value_bool, value_option=row.value_option
            )
        }
        text = _haystack(product)
        for guess in GUESSES:
            attribute = dictionary.get(guess.attribute)
            if attribute is None or attribute.pk in taken:
                continue
            if attribute.missing_parent_error(present) is not None:
                orphaned += 1
                continue
            name = next(
                (value for word, value in guess.by_word if word in text),
                guess.fallback,
            )
            value = attribute.values.filter(value=name).first()
            if value is None:
                continue
            row = ProductAttribute.objects.create(
                product=product, attribute=attribute, value_option=value
            )
            ledger.rows.append(row.pk)
            taken.add(attribute.pk)
            if not value.marks_absence:
                present.add(attribute.pk)
            filled += 1
    return [
        f"  строк разметки добавлено: {filled}",
        f"  пропущено без родителя: {orphaned}",
    ]


def seed_variants(ledger: Ledger) -> list[str]:
    """Заводит типовые размеры тем товарам, у которых их ещё нет."""
    created: list[ProductVariant] = []
    for product in Product.objects.filter(category__slug=CATEGORY_SLUG):
        taken = {
            (variant.width_mm, variant.height_mm)
            for variant in product.variants.all()
        }
        for order, (width, height) in enumerate(VARIANT_SIZES):
            if (width, height) in taken:
                continue
            variant = ProductVariant.objects.create(
                product=product,
                width_mm=width,
                height_mm=height,
                order=order,
            )
            ledger.variants.append(variant.pk)
            created.append(variant)
    repricing.reprice(
        ProductVariant.objects.filter(
            pk__in=[variant.pk for variant in created]
        )
        .select_related("product")
        .prefetch_related("values", tariffs.product_values("product__"))
    )
    return [f"  вариантов заведено: {len(created)}"]


def audit() -> list[str]:
    """Чем кончилось: сколько товаров с ценой и с калькулятором."""
    products = list(
        Product.objects.filter(category__slug=CATEGORY_SLUG).prefetch_related(
            tariffs.product_values()
        )
    )
    calculable = sum(
        1 for product in products if calculator.is_calculable(product)
    )
    priced = [product for product in products if product.price is not None]
    lines = [
        f"  товаров: {len(products)}",
        f"  с ценой: {len(priced)}",
        f"  с калькулятором: {calculable}",
    ]
    if priced:
        cheapest = min(product.price for product in priced)
        dearest = max(product.price for product in priced)
        lines.append(f"  «цена от»: {cheapest}–{dearest} ₽")
    return lines


def apply() -> list[str]:
    """Прогон: тарифы, параметры, разметка, варианты — одной транзакцией."""
    ledger = Ledger.load() or Ledger.empty()
    with transaction.atomic():
        report = ["Тарифы:", *seed_tariffs(ledger)]
        report += ["Параметры расчёта:", *seed_settings(ledger)]
        report += ["Разметка:", *seed_markup(ledger)]
        report += ["Варианты:", *seed_variants(ledger)]
    ledger.save()
    return [*report, "Итог:", *audit(), f"Отчёт прогона: {LEDGER}"]


def undo() -> list[str]:
    """Снимает ровно то, что поставил прогон."""
    ledger = Ledger.load()
    if ledger is None:
        return [f"Отчёта прогона нет ({LEDGER}) — снимать нечего."]
    with transaction.atomic():
        return _rollback(ledger)


def _rollback(ledger: Ledger) -> list[str]:
    """Тело отката — отдельной функцией, чтобы транзакция читалась."""
    variants = ProductVariant.objects.filter(pk__in=ledger.variants)
    touched = set(variants.values_list("product_id", flat=True))
    removed_variants = variants.delete()[0]
    removed_rows = ProductAttribute.objects.filter(
        pk__in=ledger.rows
    ).delete()[0]
    for key, (unit, rate, scaled) in ledger.values.items():
        AttributeValue.objects.filter(pk=int(key)).update(
            unit=unit,
            rate=Decimal(rate) if rate is not None else None,
            scaled_by_shape=scaled,
        )
    if ledger.settings_created:
        PricingSettings.objects.all().delete()
    repricing.settle_prices(touched)
    LEDGER.unlink()
    return [
        f"Снято: вариантов {removed_variants}, строк разметки {removed_rows}, "
        f"тарифов возвращено {len(ledger.values)}",
        *audit(),
    ]


def main() -> None:
    """Разбор аргументов и запуск — как у соседних скриптов."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="снять заведённое прогоном и вернуть прежние тарифы",
    )
    arguments = parser.parse_args()
    if os.environ.get("POSTGRES_HOST"):
        sys.exit(
            "Отказ: задан POSTGRES_HOST. Демонстрационные цифры "
            "заводятся только в локальную базу разработчика."
        )
    print("\n".join(undo() if arguments.undo else apply()))


if __name__ == "__main__":
    main()
