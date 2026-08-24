"""Справочник по набору владельца (тикет 22).

Проверяется поведение, а не устройство: что показала страница, что
сказала админка, какое число вернул расчёт и что оказалось в базе
после переразметки. Сама переразметка — одноразовый скрипт из
`.scratch/`; он прогоняется здесь на копии данных старого справочника.
"""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from django.test import Client

from memiro.catalog import calculator, tariffs
from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    Landing,
    LandingCondition,
    Product,
    ProductAttribute,
)

# Условные тарифы ADR-0007
GLASS_RATE = Decimal(4000)
CUTOUT_RATE = Decimal(500)
# Душевая перегородка 1 × 2 м: 2 м² стекла по 6 000 ₽ и 6 пог. м
# профиля по 1 500 ₽
PARTITION_PRICE = 21000

REPO = Path(__file__).resolve().parents[1]
REMAP = REPO / ".scratch" / "new-site" / "dictionary" / "remap.py"


def load_remap() -> ModuleType:
    """Одноразовый скрипт из `.scratch/` — он не пакет проекта."""
    if "remap" in sys.modules:
        return sys.modules["remap"]
    spec = importlib.util.spec_from_file_location("remap", REMAP)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Датаклассы скрипта ищут свои аннотации в `sys.modules`
    sys.modules["remap"] = module
    spec.loader.exec_module(module)
    return module


def page_html(client: Client, url: str) -> str:
    response = client.get(url)
    assert response.status_code == HTTPStatus.OK
    return response.content.decode()


@pytest.fixture
def shop(db: None) -> SimpleNamespace:
    """Зеркало по набору владельца: полотно, рама и подсветка.

    Тип полотна покупатель меняет в калькуляторе, и фильтра он не даёт:
    любое зеркало делают из любого полотна.
    """
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    blade = Attribute.objects.create(
        category=category,
        name="Тип полотна",
        slug="tip-polotna",
        is_customer_editable=True,
        is_filterable=False,
    )
    silver = AttributeValue.objects.create(
        attribute=blade,
        value="Серебро",
        unit=AttributeValue.Unit.SQUARE_METER,
        rate=GLASS_RATE,
    )
    AttributeValue.objects.create(
        attribute=blade, value="Графит", order=1, unit="", rate=None
    )
    frame = Attribute.objects.create(
        category=category, name="Рама", slug="frame", order=1
    )
    aluminium = AttributeValue.objects.create(
        attribute=frame, value="Алюминий"
    )
    no_frame = AttributeValue.objects.create(
        attribute=frame, value="Без рамы", marks_absence=True, order=1
    )
    colour = Attribute.objects.create(
        category=category, name="Цвет рамы", slug="frame-color", order=2
    )
    colour.parents.set([frame])
    black = AttributeValue.objects.create(attribute=colour, value="Чёрный")
    product = Product.objects.create(
        category=category,
        name="Halo Moon",
        slug="halo-moon",
        price=9000,
        is_published=True,
    )
    ProductAttribute.objects.create(
        product=product, attribute=blade, value_option=silver
    )
    ProductAttribute.objects.create(
        product=product, attribute=frame, value_option=aluminium
    )
    ProductAttribute.objects.create(
        product=product, attribute=colour, value_option=black
    )
    return SimpleNamespace(
        category=category,
        blade=blade,
        silver=silver,
        frame=frame,
        aluminium=aluminium,
        no_frame=no_frame,
        colour=colour,
        product=product,
    )


def test_unfilterable_attribute_gives_no_group(
    client: Client, shop: SimpleNamespace
) -> None:
    """По типу полотна фильтр в сайдбаре не строится."""
    html = page_html(client, "/catalog/zerkala/")

    assert "Рама" in html
    assert "Тип полотна" not in html


def test_unfilterable_attribute_does_not_narrow(
    client: Client, shop: SimpleNamespace
) -> None:
    """Параметром типа полотна выдачу не сузить — его просто нет.

    Иначе адрес `?tip-polotna=…` сужал бы каталог мимо сайдбара, и
    посетитель видел бы сужение, которое нечем снять.
    """
    graphite = shop.blade.values.get(value="Графит")

    html = page_html(client, f"/catalog/zerkala/?tip-polotna={graphite.pk}")

    assert "Halo Moon" in html
    assert "Сбросить всё" not in html


def test_landing_on_unfilterable_attribute_rejected(
    shop: SimpleNamespace,
) -> None:
    """Посадочная по типу полотна не заводится (ADR-0003)."""
    landing = Landing.objects.create(
        category=shop.category,
        slug="zerkala-iz-serebra",
        title="Зеркала из серебра",
        heading="Зеркала из серебра",
        description="",
    )
    condition = LandingCondition(
        landing=landing, attribute=shop.blade, value_option=shop.silver
    )

    with pytest.raises(ValidationError) as error:
        condition.full_clean()

    assert "фильтр не строится" in str(error.value)


def test_absence_value_is_not_a_parent(shop: SimpleNamespace) -> None:
    """«Без рамы» не родитель: цвета рамы у такого зеркала не бывает.

    Иначе безрамное зеркало вечно ждало бы цвет рамы, и калькулятор
    у него не включился бы никогда.
    """
    frameless = Product.objects.create(
        category=shop.category, name="Bare", slug="bare"
    )
    ProductAttribute.objects.create(
        product=frameless,
        attribute=shop.blade,
        value_option=shop.silver,
    )
    ProductAttribute.objects.create(
        product=frameless, attribute=shop.frame, value_option=shop.no_frame
    )

    assert calculator.missing_for_calculation(frameless) == ()


def test_absence_value_costs_nothing(shop: SimpleNamespace) -> None:
    """Отсутствие признака не расходуется и тарифа не носит."""
    value = AttributeValue(
        attribute=shop.frame,
        value="Без рамы совсем",
        marks_absence=True,
        unit=AttributeValue.Unit.PIECE,
        rate=Decimal(100),
    )

    with pytest.raises(ValidationError) as error:
        value.full_clean()

    assert "не стоит денег" in str(error.value)


def test_unmarked_product_gets_no_calculator(
    client: Client, shop: SimpleNamespace
) -> None:
    """Товар с незаполненным обязательным атрибутом расчёт не включает."""
    bare = Product.objects.create(
        category=shop.category,
        name="Без разметки",
        slug="bez-razmetki",
        is_published=True,
    )

    assert not calculator.is_calculable(bare)
    assert calculator.missing_for_calculation(bare) == ("Тип полотна", "Рама")
    # Карточка вместо калькулятора обходится вариантами и заявкой
    assert "data-calc" not in page_html(
        client, "/catalog/zerkala/bez-razmetki/"
    )


def test_admin_names_what_calculation_lacks(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Чего именно не хватает, админка говорит вслух, а не молчит."""
    Product.objects.create(
        category=shop.category, name="Без разметки", slug="bez-razmetki"
    )

    html = page_html(admin_client, "/admin/catalog/product/")

    assert "не включается: Тип полотна" in html


def test_admin_says_calculator_is_on(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    html = page_html(
        admin_client, f"/admin/catalog/product/{shop.product.pk}/change/"
    )

    assert "включён" in html


def test_untariffed_product_is_named_so(shop: SimpleNamespace) -> None:
    """Разметка есть, тарифов нет — причина названа отдельно от пробелов."""
    graphite = shop.blade.values.get(value="Графит")
    ProductAttribute.objects.filter(
        product=shop.product, attribute=shop.blade
    ).update(value_option=graphite)

    assert calculator.missing_for_calculation(shop.product) == (
        calculator.NO_TARIFFS,
    )


@pytest.fixture
def cutout(shop: SimpleNamespace) -> Attribute:
    """Вырез: число у товара, тариф — одна строка справочника."""
    attribute = Attribute.objects.create(
        category=shop.category,
        name="Вырез",
        slug="cutout",
        kind=Attribute.Kind.NUMBER,
        is_filterable=False,
        order=3,
    )
    AttributeValue.objects.create(
        attribute=attribute,
        value="Вырез",
        unit=AttributeValue.Unit.PIECE,
        rate=CUTOUT_RATE,
    )
    return attribute


def price_of(product: Product, *, width_mm: int, height_mm: int) -> int:
    fresh = Product.objects.prefetch_related(tariffs.product_values()).get(
        pk=product.pk
    )
    return tariffs.price(
        tariffs.configuration(fresh, width_mm=width_mm, height_mm=height_mm)
    ).total


def test_cutout_count_multiplies_its_tariff(
    shop: SimpleNamespace, cutout: Attribute
) -> None:
    """Два выреза стоят вдвое: число у товара — это количество."""
    without = price_of(shop.product, width_mm=1000, height_mm=1000)
    ProductAttribute.objects.create(
        product=shop.product, attribute=cutout, value_number=Decimal(2)
    )

    with_two = price_of(shop.product, width_mm=1000, height_mm=1000)

    assert with_two - without == 2 * CUTOUT_RATE


def test_missing_cutout_is_not_a_gap(
    shop: SimpleNamespace, cutout: Attribute
) -> None:
    """Незаполненный вырез значит, что выреза нет, а не что цена неполна."""
    assert calculator.missing_for_calculation(shop.product) == ()


def test_number_attribute_keeps_one_tariff(
    shop: SimpleNamespace, cutout: Attribute
) -> None:
    """Вторая строка у числового атрибута — чей тариф считать?"""
    second = AttributeValue(
        attribute=cutout,
        value="Большой вырез",
        unit=AttributeValue.Unit.PIECE,
        rate=Decimal(900),
    )

    with pytest.raises(ValidationError) as error:
        second.full_clean()

    assert "строка справочника одна" in str(error.value)


def test_new_category_needs_no_developer(db: None) -> None:
    """Обещание ADR-0002: категория, её атрибуты и тарифы — данные.

    Душевые перегородки заводятся тем же справочником, что и зеркала,
    и считаются тем же движком — без единой строки кода.
    """
    category = Category.objects.create(
        name="Душевые перегородки", slug="dushevye"
    )
    glass = Attribute.objects.create(
        category=category, name="Стекло", slug="steklo"
    )
    clear = AttributeValue.objects.create(
        attribute=glass,
        value="Прозрачное",
        unit=AttributeValue.Unit.SQUARE_METER,
        rate=Decimal(6000),
    )
    profile = Attribute.objects.create(
        category=category, name="Профиль", slug="profil", order=1
    )
    chrome = AttributeValue.objects.create(
        attribute=profile,
        value="Хром",
        unit=AttributeValue.Unit.LINEAR_METER,
        rate=Decimal(1500),
    )
    partition = Product.objects.create(
        category=category, name="Cascade", slug="cascade"
    )
    ProductAttribute.objects.create(
        product=partition, attribute=glass, value_option=clear
    )
    ProductAttribute.objects.create(
        product=partition, attribute=profile, value_option=chrome
    )

    assert (
        price_of(partition, width_mm=1000, height_mm=2000) == PARTITION_PRICE
    )
    assert calculator.is_calculable(partition)


@pytest.fixture
def legacy(db: None) -> SimpleNamespace:
    """Справочник и разметка старого сайта — то, что застаёт скрипт."""
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    attributes = {}
    values = {}
    legacy_set = {
        "location": ("Расположение", ("Настенное", "Напольное")),
        "form": ("Форма", ("Прямоугольное", "Круглое")),
        "backlight": ("Подсветка", ("С подсветкой", "Без подсветки")),
        "frame": ("Рама", ("В раме", "Без рамы")),
        "frame-color": ("Цвет рамы", ("Чёрный",)),
        "frame-material": ("Материал рамы", ("Алюминий", "Другое")),
    }
    for order, (slug, (name, labels)) in enumerate(legacy_set.items()):
        attribute = Attribute.objects.create(
            category=category, name=name, slug=slug, order=order
        )
        attributes[slug] = attribute
        for label in labels:
            values[slug, label] = AttributeValue.objects.create(
                attribute=attribute, value=label
            )

    def mirror(slug: str, **marks: str) -> Product:
        product = Product.objects.create(
            category=category, name=slug, slug=slug
        )
        for attribute_slug, label in marks.items():
            ProductAttribute.objects.create(
                product=product,
                attribute=attributes[attribute_slug],
                value_option=values[attribute_slug, label],
            )
        return product

    aluminium = mirror(
        "alu",
        location="Настенное",
        form="Прямоугольное",
        backlight="С подсветкой",
        frame="В раме",
        **{"frame-material": "Алюминий", "frame-color": "Чёрный"},
    )
    baguette = mirror(
        "baget",
        location="Настенное",
        form="Круглое",
        backlight="Без подсветки",
        frame="В раме",
        **{"frame-material": "Другое"},
    )
    floor = mirror(
        "floor",
        location="Напольное",
        form="Прямоугольное",
        backlight="Без подсветки",
        frame="Без рамы",
    )
    return SimpleNamespace(
        category=category,
        aluminium=aluminium,
        baguette=baguette,
        floor=floor,
    )


def marks(product: Product) -> dict[str, str]:
    """Разметка товара словарём «слаг атрибута → значение»."""
    return {
        row.attribute.slug: row.display_value
        for row in product.attribute_values.select_related(
            "attribute", "value_option"
        )
    }


def test_remap_brings_owner_set(legacy: SimpleNamespace) -> None:
    """Справочник приведён к набору владельца, старого в нём нет."""
    remap = load_remap()

    remap.run()

    slugs = set(
        Attribute.objects.filter(category=legacy.category).values_list(
            "slug", flat=True
        )
    )
    assert slugs == {spec.slug for spec in remap.OWNER_SET}
    blade = Attribute.objects.get(category=legacy.category, slug="tip-polotna")
    assert not blade.is_filterable
    assert blade.is_customer_editable
    backlight = Attribute.objects.get(
        category=legacy.category, slug="backlight"
    )
    assert backlight.values.get(value="Без подсветки").marks_absence


def test_remap_carries_over_the_unambiguous(
    legacy: SimpleNamespace,
) -> None:
    """Алюминиевая рама и напольное крепление переезжают скриптом."""
    remap = load_remap()

    remap.run()

    assert marks(legacy.aluminium)["frame"] == "Алюминий"
    assert marks(legacy.floor)["mount"] == "На ножке"
    # Форма и цвет рамы остаются как есть
    assert marks(legacy.aluminium)["form"] == "Прямоугольное"
    assert marks(legacy.aluminium)["frame-color"] == "Чёрный"


def test_remap_clears_the_ambiguous(legacy: SimpleNamespace) -> None:
    """Двусмысленное снимается и уходит в отчёт, а не угадывается.

    «С подсветкой» не говорит, контурная лента или фронтальная, а от
    этого зависит, считать по периметру или по площади.
    """
    remap = load_remap()

    report = remap.run()

    assert "backlight" not in marks(legacy.aluminium)
    assert "frame" not in marks(legacy.baguette)
    assert legacy.aluminium.slug in report.cleared["Подсветка"]
    assert legacy.baguette.slug in report.cleared["Рама"]
    assert legacy.aluminium.slug in report.unfilled["Подсветка"]


def test_remap_leaves_no_calculator_on(legacy: SimpleNamespace) -> None:
    """Пока разметка неполна, калькулятор не включается ни у кого."""
    remap = load_remap()

    remap.run()

    assert not any(
        calculator.is_calculable(product)
        for product in Product.objects.filter(category=legacy.category)
    )


def test_remap_prunes_values_outside_the_set(
    legacy: SimpleNamespace,
) -> None:
    """Приведение к набору — это и значения, а не одни атрибуты."""
    remap = load_remap()

    remap.run()

    values = {
        (row.attribute.slug, row.value)
        for row in AttributeValue.objects.select_related("attribute").filter(
            attribute__category=legacy.category
        )
    }
    assert values == {
        (spec.slug, value.value)
        for spec in remap.OWNER_SET
        for value in spec.values
    }


def test_remap_keeps_a_stray_value_that_products_hold(
    legacy: SimpleNamespace,
) -> None:
    """Занятое лишнее значение не стирается молча — оно уходит в отчёт.

    Удалить его значило бы стереть заодно разметку товаров, а решить
    за владельца, куда её переназначить, нельзя.
    """
    colour = Attribute.objects.get(
        category=legacy.category, slug="frame-color"
    )
    wood = AttributeValue.objects.create(attribute=colour, value="Дерево")
    ProductAttribute.objects.filter(
        product=legacy.baguette, attribute=colour
    ).delete()
    ProductAttribute.objects.create(
        product=legacy.baguette, attribute=colour, value_option=wood
    )
    remap = load_remap()

    report = remap.run()

    assert AttributeValue.objects.filter(pk=wood.pk).exists()
    assert report.strays["Цвет рамы: Дерево"] == [legacy.baguette.slug]


def test_remap_repeats_without_damage(legacy: SimpleNamespace) -> None:
    """Повторный прогон ничего не портит и ничего не переносит дважды."""
    remap = load_remap()
    remap.run()
    blade = Attribute.objects.get(category=legacy.category, slug="tip-polotna")
    silver = blade.values.get(value="Серебро")
    ProductAttribute.objects.create(
        product=legacy.floor, attribute=blade, value_option=silver
    )
    before = marks(legacy.floor)

    again = remap.run()

    assert again.carried == 0
    # Проставленное владельцем между прогонами остаётся на месте
    assert marks(legacy.floor) == before
    assert marks(legacy.aluminium)["frame"] == "Алюминий"
