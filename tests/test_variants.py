"""Предпосчитанный вариант (тикет 17): цена от движка, вывод на карточке.

Цена варианта владельцем не вводится — её считает движок из тарифов
справочника. Поэтому проверяется не устройство сборки, а поведение:
какое число оказалось у варианта, что показала карточка и что
случилось с ценами после правки тарифа.
"""

from __future__ import annotations

import re
from decimal import Decimal
from http import HTTPStatus
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from memiro.catalog import repricing
from memiro.catalog.formatting import rub
from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    PricingSettings,
    Product,
    ProductAttribute,
    ProductVariant,
)

# Условные тарифы ADR-0007: полотно 4 000 ₽/м², графит 5 000 ₽/м²,
# контурная подсветка 2 500 ₽/пог. м
SILVER_800_600 = 9000
SILVER_WITHOUT_ILLUMINATION = 2000
ILLUMINATION_ONLY = 7000
GRAPHITE_1200_700 = 13700
SILVER_AFTER_RAISE = 9900
MIN_ORDER_TOTAL = 20000

LOC = re.compile(r"<loc>")


@pytest.fixture
def shop(db: None) -> SimpleNamespace:
    """Зеркало с контурной подсветкой и двумя типами полотна.

    Подсветку покупатель не меняет — она стоит у товара и входит
    в расчёт каждого варианта; тип полотна вариант выбирает сам.
    """
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    blade = Attribute.objects.create(
        category=category,
        name="Тип полотна",
        slug="tip-polotna",
        is_customer_editable=True,
    )
    silver = AttributeValue.objects.create(
        attribute=blade,
        value="Серебро",
        unit=AttributeValue.Unit.SQUARE_METER,
        rate=Decimal(4000),
        scaled_by_shape=True,
    )
    graphite = AttributeValue.objects.create(
        attribute=blade,
        value="Графит",
        unit=AttributeValue.Unit.SQUARE_METER,
        rate=Decimal(5000),
        scaled_by_shape=True,
    )
    illumination = Attribute.objects.create(
        category=category,
        name="Подсветка",
        slug="podsvetka",
        order=1,
    )
    contour = AttributeValue.objects.create(
        attribute=illumination,
        value="Контурная",
        unit=AttributeValue.Unit.LINEAR_METER,
        rate=Decimal(2500),
    )
    product = Product.objects.create(
        category=category,
        name="Halo Moon",
        slug="halo-moon",
        price=1,
        is_published=True,
    )
    ProductAttribute.objects.create(
        product=product, attribute=illumination, value_option=contour
    )
    return SimpleNamespace(
        category=category,
        product=product,
        blade=blade,
        silver=silver,
        graphite=graphite,
        illumination=illumination,
        contour=contour,
    )


def add_variant(
    shop: SimpleNamespace,
    width_mm: int,
    height_mm: int,
    value: AttributeValue,
    order: int = 0,
) -> ProductVariant:
    variant = ProductVariant.objects.create(
        product=shop.product,
        width_mm=width_mm,
        height_mm=height_mm,
        order=order,
    )
    variant.values.add(value)
    return variant


def product_page(client: Client, shop: SimpleNamespace) -> str:
    response = client.get(
        f"/catalog/{shop.category.slug}/{shop.product.slug}/"
    )

    assert response.status_code == HTTPStatus.OK
    return response.content.decode()


# --- цена варианта ----------------------------------------------------


@pytest.mark.django_db
def test_variant_price_is_computed_from_the_dictionary(
    shop: SimpleNamespace,
) -> None:
    """800×600 серебро: 0,48 м² полотна и 2,8 пог. м ленты."""
    variant = add_variant(shop, 800, 600, shop.silver)

    variant.refresh_from_db()

    assert variant.price == SILVER_800_600


@pytest.mark.django_db
def test_variant_price_counts_the_product_own_attributes(
    shop: SimpleNamespace,
) -> None:
    """Подсветка стоит у товара, а платит за неё каждый вариант."""
    variant = add_variant(shop, 800, 600, shop.silver)
    variant.refresh_from_db()
    with_illumination = variant.price

    shop.product.attribute_values.all().delete()
    variant.refresh_from_db()

    assert variant.price < with_illumination


@pytest.mark.django_db
def test_variant_value_wins_over_the_product_one(
    shop: SimpleNamespace,
) -> None:
    """Полотно товара — умолчание; вариант ставит своё, а не второе."""
    ProductAttribute.objects.create(
        product=shop.product,
        attribute=shop.blade,
        value_option=shop.silver,
    )
    variant = add_variant(shop, 1200, 700, shop.graphite)

    variant.refresh_from_db()

    assert variant.price == GRAPHITE_1200_700


@pytest.mark.django_db
def test_a_tariff_change_reaches_the_variants(
    shop: SimpleNamespace,
) -> None:
    """Иначе таблица на карточке разошлась бы с расчётом."""
    variant = add_variant(shop, 800, 600, shop.silver)

    shop.silver.rate = Decimal(6000)
    shop.silver.save()
    variant.refresh_from_db()

    assert variant.price == SILVER_AFTER_RAISE


@pytest.mark.django_db
def test_a_value_taken_off_the_variant_reaches_the_price(
    shop: SimpleNamespace,
) -> None:
    """Связь правят и со стороны справочника — цена едет и оттуда."""
    variant = add_variant(shop, 800, 600, shop.silver)

    shop.silver.variant_selections.remove(variant)
    variant.refresh_from_db()

    assert variant.price == ILLUMINATION_ONLY


@pytest.mark.django_db
def test_pricing_settings_reach_the_variants(shop: SimpleNamespace) -> None:
    """Минимальная сумма заказа поднимает и цену варианта."""
    variant = add_variant(shop, 800, 600, shop.silver)

    PricingSettings.objects.create(min_order_total=MIN_ORDER_TOTAL)
    variant.refresh_from_db()

    assert variant.price == MIN_ORDER_TOTAL


@pytest.mark.django_db
def test_repricing_a_batch_does_not_query_per_variant(
    shop: SimpleNamespace,
) -> None:
    """Правка тарифа пересчитывает все варианты сайта — их сотни.

    Считается не число запросов (оно зависит от устройства сборки),
    а его рост: от количества вариантов он зависеть не должен.
    """
    for offset in range(2):
        add_variant(shop, 800 + offset, 600, shop.silver)
    few = _queries_of_a_sweep()

    for offset in range(2, 8):
        add_variant(shop, 800 + offset, 600, shop.silver)
    many = _queries_of_a_sweep()

    assert many == few


def _queries_of_a_sweep() -> int:
    """Сколько запросов стоит пересчёт всех вариантов сайта."""
    with CaptureQueriesContext(connection) as queries:
        repricing.reprice(repricing.all_variants())
    return len(queries)


# --- карточка товара --------------------------------------------------


@pytest.mark.django_db
def test_product_page_lists_variants_in_the_owner_order(
    client: Client, shop: SimpleNamespace
) -> None:
    add_variant(shop, 800, 600, shop.silver, order=1)
    add_variant(shop, 1200, 700, shop.graphite, order=0)

    html = product_page(client, shop)
    graphite_row = html.index("1200 × 700 мм")

    assert f"{rub(GRAPHITE_1200_700)} ₽" in html
    assert f"{rub(SILVER_800_600)} ₽" in html
    assert graphite_row < html.index("800 × 600 мм")


@pytest.mark.django_db
def test_product_without_variants_shows_no_table(
    client: Client, shop: SimpleNamespace
) -> None:
    html = product_page(client, shop)

    assert "Типовые размеры" not in html


@pytest.mark.django_db
def test_variants_stay_out_of_the_sitemap(
    client: Client, shop: SimpleNamespace
) -> None:
    """У варианта нет своего адреса — обходить нечего."""
    before = len(LOC.findall(client.get("/sitemap.xml").content.decode()))

    add_variant(shop, 800, 600, shop.silver)
    after = len(LOC.findall(client.get("/sitemap.xml").content.decode()))

    assert after == before


# --- админка ----------------------------------------------------------


def product_payload(
    shop: SimpleNamespace, **extra: object
) -> dict[str, object]:
    """Форма товара для POST в админку, инлайны пустые."""
    payload: dict[str, object] = {
        "category": shop.category.pk,
        "name": "Зеркало «Луна»",
        "slug": "luna",
        "price": "1",
        "description": "",
        "article": "",
        "order": "0",
        "gallery-TOTAL_FORMS": "0",
        "gallery-INITIAL_FORMS": "0",
        "attribute_values-TOTAL_FORMS": "0",
        "attribute_values-INITIAL_FORMS": "0",
        "variants-TOTAL_FORMS": "0",
        "variants-INITIAL_FORMS": "0",
        "_save": "",
    }
    payload.update(extra)
    return payload


@pytest.mark.django_db
def test_owner_edits_variants_inline_and_never_types_a_price(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Инлайн варианта в карточке товара есть, поля цены в нём нет."""
    response = admin_client.get(
        f"/admin/catalog/product/{shop.product.pk}/change/"
    )
    html = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert 'name="variants-0-width_mm"' in html
    assert 'name="variants-0-price"' not in html


@pytest.mark.django_db
def test_variant_saved_from_the_admin_gets_its_price(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Владелец задаёт размеры и полотно — цену проставляет движок."""
    response = admin_client.post(
        "/admin/catalog/product/add/",
        product_payload(
            shop,
            **{
                "variants-TOTAL_FORMS": "1",
                "variants-0-width_mm": "800",
                "variants-0-height_mm": "600",
                "variants-0-values": [str(shop.silver.pk)],
                "variants-0-order": "0",
            },
        ),
    )

    assert response.status_code == HTTPStatus.FOUND
    variant = ProductVariant.objects.get(product__slug="luna")
    assert variant.price == SILVER_WITHOUT_ILLUMINATION


@pytest.mark.django_db
def test_two_values_of_one_attribute_are_rejected(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Серебро и графит сразу — это два варианта, а не один."""
    response = admin_client.post(
        "/admin/catalog/product/add/",
        product_payload(
            shop,
            **{
                "variants-TOTAL_FORMS": "1",
                "variants-0-width_mm": "800",
                "variants-0-height_mm": "600",
                "variants-0-values": [
                    str(shop.silver.pk),
                    str(shop.graphite.pk),
                ],
                "variants-0-order": "0",
            },
        ),
    )

    assert response.status_code == HTTPStatus.OK
    assert not ProductVariant.objects.exists()
    assert "Тип полотна" in response.content.decode()


@pytest.mark.django_db
def test_value_of_a_foreign_category_is_rejected(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Вариант зеркала не собрать из атрибутов душевых перегородок."""
    other = Category.objects.create(name="Перегородки", slug="peregorodki")
    glass = Attribute.objects.create(
        category=other, name="Стекло", slug="steklo"
    )
    matte = AttributeValue.objects.create(attribute=glass, value="Матовое")

    response = admin_client.post(
        "/admin/catalog/product/add/",
        product_payload(
            shop,
            **{
                "variants-TOTAL_FORMS": "1",
                "variants-0-width_mm": "800",
                "variants-0-height_mm": "600",
                "variants-0-values": [str(matte.pk)],
                "variants-0-order": "0",
            },
        ),
    )

    assert response.status_code == HTTPStatus.OK
    assert not ProductVariant.objects.exists()
    assert "Стекло" in response.content.decode()


# --- справочник -------------------------------------------------------


@pytest.mark.django_db
def test_shape_factor_needs_something_to_multiply(
    shop: SimpleNamespace,
) -> None:
    """Умножать коэффициентом формы нечего у бесплатного значения."""
    with pytest.raises(ValidationError):
        AttributeValue(
            attribute=shop.blade,
            value="Бронза",
            scaled_by_shape=True,
        ).full_clean()
    with pytest.raises(ValidationError):
        AttributeValue(
            attribute=shop.blade,
            value="Круглое",
            unit=AttributeValue.Unit.FACTOR,
            rate=Decimal("1.5"),
            scaled_by_shape=True,
        ).full_clean()
