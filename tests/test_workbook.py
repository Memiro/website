"""Книга расчёта: повторяет ли она справочник и движок.

Формулы таблицы здесь не считаются — их считает Excel, а не Python.
Проверяется то, из-за чего книга врёт молча: не тот тариф в
справочнике, не тот ключ у строки, разъехавшиеся подписи единиц и
итоги «Сверки», которые обязаны совпадать с движком.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from memiro import pricing
from memiro.catalog import tariffs, workbook
from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    PricingSettings,
    Product,
    ProductAttribute,
)

GLASS_RATE = Decimal(4500)
CONTOUR_RATE = Decimal(2500)
CUTOUT_RATE = Decimal(1200)
ROUND_FACTOR = Decimal("1.5")
CUTOUTS = Decimal(2)


@pytest.fixture
def category(db: None) -> Category:
    """Категория со справочником, которого хватает на расчёт."""
    made = Category.objects.create(name="Зеркала", slug="zerkala")
    PricingSettings.objects.create(
        pk=PricingSettings.SINGLETON_PK,
        min_area_m2=Decimal("0.250"),
        min_order_total=2000,
        max_long_side_mm=3200,
        max_short_side_mm=2500,
    )
    glass = Attribute.objects.create(
        category=made,
        name="Тип полотна",
        slug="glass",
        is_customer_editable=True,
    )
    AttributeValue.objects.create(
        attribute=glass,
        value="Серебро",
        unit=AttributeValue.Unit.SQUARE_METER,
        rate=GLASS_RATE,
        scaled_by_shape=True,
    )
    shape = Attribute.objects.create(
        category=made, name="Форма", slug="shape", order=1
    )
    AttributeValue.objects.create(
        attribute=shape,
        value="Круглое",
        unit=AttributeValue.Unit.FACTOR,
        rate=ROUND_FACTOR,
    )
    light = Attribute.objects.create(
        category=made, name="Подсветка", slug="light", order=2
    )
    AttributeValue.objects.create(
        attribute=light,
        value="Контурная",
        unit=AttributeValue.Unit.LINEAR_METER,
        rate=CONTOUR_RATE,
    )
    AttributeValue.objects.create(
        attribute=light, value="Без подсветки", marks_absence=True
    )
    cutout = Attribute.objects.create(
        category=made,
        name="Вырез",
        slug="cutout",
        kind=Attribute.Kind.NUMBER,
        order=3,
    )
    AttributeValue.objects.create(
        attribute=cutout,
        value="Вырез",
        unit=AttributeValue.Unit.PIECE,
        rate=CUTOUT_RATE,
    )
    return made


@pytest.fixture
def product(category: Category) -> Product:
    """Размеченное зеркало: круглое, серебро, контурная, два выреза."""
    made = Product.objects.create(
        category=category, name="Зеркало Halo", slug="halo"
    )
    markup = {
        "Тип полотна": "Серебро",
        "Форма": "Круглое",
        "Подсветка": "Контурная",
    }
    for name, value in markup.items():
        attribute = category.attributes.get(name=name)
        ProductAttribute.objects.create(
            product=made,
            attribute=attribute,
            value_option=attribute.values.get(value=value),
        )
    ProductAttribute.objects.create(
        product=made,
        attribute=category.attributes.get(name="Вырез"),
        value_number=CUTOUTS,
    )
    return made


def test_dictionary_carries_every_value(category: Category) -> None:
    """Справочник книги — весь справочник админки, без потерь."""
    sheet = workbook.build(category)[workbook.DICTIONARY]
    written = {
        (row[0].value, row[1].value)
        for row in sheet.iter_rows(min_row=workbook.DATA_START, max_col=2)
        if row[0].value
    }
    assert written == {
        (value.attribute.name, value.value)
        for value in AttributeValue.objects.select_related("attribute")
    }


def test_key_column_matches_calculation_lookup(
    category: Category,
) -> None:
    """Ключ справочника собирается так же, как его ищет «Расчёт».

    Разойдись они — расчёт не нашёл бы строку и молча показал ноль
    вместо цены.
    """
    sheet = workbook.build(category)[workbook.DICTIONARY]
    for row in sheet.iter_rows(min_row=workbook.DATA_START, max_col=8):
        if row[0].value is None:
            continue
        assert row[7].value == f"{row[0].value} | {row[1].value}"


def test_units_are_spelled_the_way_formulas_expect(
    category: Category,
) -> None:
    """Подписи единиц — те же, что стоят в формулах книги."""
    sheet = workbook.build(category)[workbook.DICTIONARY]
    spelled = {
        row[2].value
        for row in sheet.iter_rows(min_row=workbook.DATA_START, max_col=3)
        if row[0].value
    }
    known = set(workbook.UNIT_LABELS.values()) | {workbook.FREE_LABEL}
    assert spelled <= known


def test_check_sheet_repeats_the_engine(product: Product) -> None:
    """«Сверка» показывает ровно то, что считает движок сайта."""
    sheet = workbook.build(product.category, product=product)["Сверка"]
    limits = tariffs.limits_from_settings()
    for row, (width, height) in enumerate(
        workbook.CHECK_SIZES, workbook.DATA_START
    ):
        expected = tariffs.price(
            tariffs.configuration(product, width_mm=width, height_mm=height),
            limits=limits,
        )
        assert sheet.cell(row=row, column=4).value == expected.total


def test_product_markup_becomes_the_defaults(product: Product) -> None:
    """Умолчания книги — разметка товара, а не первое попавшееся."""
    sheet = workbook.build(product.category, product=product)["Расчёт"]
    layout = workbook.Layout(product.category.attributes.count())
    defaults = {
        sheet.cell(row=row, column=1).value: sheet.cell(
            row=row, column=2
        ).value
        for row in range(layout.first, layout.last + 1)
    }
    assert defaults["Тип полотна"] == "Серебро"
    assert defaults["Подсветка"] == "Контурная"


def test_cutout_quantity_comes_from_the_product(
    product: Product,
) -> None:
    """Числовой атрибут приносит в книгу своё количество."""
    sheet = workbook.build(product.category, product=product)["Расчёт"]
    layout = workbook.Layout(product.category.attributes.count())
    quantities = {
        sheet.cell(row=row, column=1).value: sheet.cell(
            row=row, column=4
        ).value
        for row in range(layout.first, layout.last + 1)
    }
    assert quantities["Вырез"] == CUTOUTS


def test_rounding_step_is_the_engine_one(category: Category) -> None:
    """Шаг округления в книге — тот же, которым округляет движок."""
    sheet = workbook.build(category)[workbook.SETTINGS_SHEET]
    steps = [
        row[1].value
        for row in sheet.iter_rows(min_row=workbook.DATA_START, max_col=2)
        if row[0].value == "Шаг округления итога, ₽"
    ]
    assert steps == [pricing.ROUNDING_STEP]
