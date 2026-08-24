"""Цена товара выводится из вариантов (тикет 18).

Владелец её не вводит: «от X ₽» на витрине — цена самого дешёвого
предпосчитанного варианта. Товар, которому вариантов не завели, цены
не имеет вовсе и молчит о ней везде: на плитке, на карточке, в
разметке, в границах диапазона и в сортировке «дешевле».

Проверяется поведение витрины, а не устройство пересчёта: какое число
увидел покупатель и что случилось с ним после правки вариантов.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from http import HTTPStatus
from types import SimpleNamespace

import pytest
from django.test import Client

from memiro.catalog.formatting import rub
from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    Product,
    ProductVariant,
)

# Условные тарифы ADR-0007: полотно 4 000 ₽/м²
SMALL_600_400 = 1000
LARGE_1200_800 = 3900
SEAM_PRICE = 7700

# Цена, вписанная в поле мимо пересчёта: так проверяется шов
PLACEHOLDER = 1

LD_JSON = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL
)


@pytest.fixture
def shop(db: None) -> SimpleNamespace:
    """Категория, зеркало с одним полотном и второе — без вариантов."""
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    blade = Attribute.objects.create(
        category=category, name="Тип полотна", slug="tip-polotna"
    )
    silver = AttributeValue.objects.create(
        attribute=blade,
        value="Серебро",
        unit=AttributeValue.Unit.SQUARE_METER,
        rate=Decimal(4000),
    )
    priced = Product.objects.create(
        category=category,
        name="Halo Moon",
        slug="halo-moon",
        is_published=True,
    )
    bare = Product.objects.create(
        category=category,
        name="View Match",
        slug="view-match",
        is_published=True,
        order=1,
    )
    return SimpleNamespace(
        category=category, silver=silver, priced=priced, bare=bare
    )


def add_variant(
    product: Product,
    width_mm: int,
    height_mm: int,
    value: AttributeValue,
) -> ProductVariant:
    variant = ProductVariant.objects.create(
        product=product, width_mm=width_mm, height_mm=height_mm
    )
    variant.values.add(value)
    return variant


def page(client: Client, url: str) -> str:
    response = client.get(url)

    assert response.status_code == HTTPStatus.OK
    return response.content.decode()


def category_page(
    client: Client, shop: SimpleNamespace, query: str = ""
) -> str:
    return page(client, f"/catalog/{shop.category.slug}/{query}")


def product_page(client: Client, product: Product) -> str:
    return page(client, f"/catalog/{product.category.slug}/{product.slug}/")


# --- цена товара ------------------------------------------------------


@pytest.mark.django_db
def test_product_price_is_the_price_of_its_cheapest_variant(
    shop: SimpleNamespace,
) -> None:
    add_variant(shop.priced, 1200, 800, shop.silver)
    add_variant(shop.priced, 600, 400, shop.silver)

    shop.priced.refresh_from_db()

    assert shop.priced.price == SMALL_600_400


@pytest.mark.django_db
def test_a_new_cheaper_variant_lowers_the_product_price(
    shop: SimpleNamespace,
) -> None:
    add_variant(shop.priced, 1200, 800, shop.silver)

    add_variant(shop.priced, 600, 400, shop.silver)
    shop.priced.refresh_from_db()

    assert shop.priced.price == SMALL_600_400


@pytest.mark.django_db
def test_editing_the_cheapest_variant_reaches_the_product_price(
    shop: SimpleNamespace,
) -> None:
    variant = add_variant(shop.priced, 600, 400, shop.silver)

    variant.width_mm, variant.height_mm = 1200, 800
    variant.save()
    shop.priced.refresh_from_db()

    assert shop.priced.price == LARGE_1200_800


@pytest.mark.django_db
def test_deleting_the_cheapest_variant_raises_the_product_price(
    shop: SimpleNamespace,
) -> None:
    cheapest = add_variant(shop.priced, 600, 400, shop.silver)
    add_variant(shop.priced, 1200, 800, shop.silver)

    cheapest.delete()
    shop.priced.refresh_from_db()

    assert shop.priced.price == LARGE_1200_800


@pytest.mark.django_db
def test_deleting_the_last_variant_leaves_the_product_without_a_price(
    shop: SimpleNamespace,
) -> None:
    """Заглушки на месте цены не остаётся — остаётся пусто."""
    variant = add_variant(shop.priced, 600, 400, shop.silver)

    variant.delete()
    shop.priced.refresh_from_db()

    assert shop.priced.price is None


@pytest.mark.django_db
def test_a_tariff_change_reaches_the_product_price(
    shop: SimpleNamespace,
) -> None:
    """Тариф правят в справочнике — витрина не отстаёт."""
    add_variant(shop.priced, 600, 400, shop.silver)

    shop.silver.rate = Decimal(8000)
    shop.silver.save()
    shop.priced.refresh_from_db()

    assert shop.priced.price == SMALL_600_400 * 2


@pytest.mark.django_db
def test_a_product_without_variants_has_no_price(
    shop: SimpleNamespace,
) -> None:
    add_variant(shop.priced, 600, 400, shop.silver)

    shop.bare.refresh_from_db()

    assert shop.bare.price is None


# --- витрина ----------------------------------------------------------


@pytest.mark.django_db
def test_catalog_card_shows_the_cheapest_variant_price(
    client: Client, shop: SimpleNamespace
) -> None:
    add_variant(shop.priced, 1200, 800, shop.silver)
    add_variant(shop.priced, 600, 400, shop.silver)

    html = category_page(client, shop)

    assert f"от {rub(SMALL_600_400)} ₽" in html
    assert f"от {rub(LARGE_1200_800)} ₽" not in html


@pytest.mark.django_db
def test_a_product_without_variants_shows_no_price(
    client: Client, shop: SimpleNamespace
) -> None:
    """Ни на плитке, ни на карточке — молчание, а не «от 1 ₽»."""
    add_variant(shop.priced, 600, 400, shop.silver)

    card = category_page(client, shop)
    detail = product_page(client, shop.bare)

    # Плитка с ценой в категории ровно одна — у товара с вариантом
    assert card.count('class="price"') == 1
    assert "price-now" not in detail
    assert "цена минимальной конфигурации" not in detail


@pytest.mark.django_db
def test_a_product_without_a_price_offers_nothing_in_the_markup(
    client: Client, shop: SimpleNamespace
) -> None:
    """lowPrice взять неоткуда — предложения в разметке нет."""
    detail = product_page(client, shop.bare)
    product_data = next(
        data
        for data in (json.loads(raw) for raw in LD_JSON.findall(detail))
        if data.get("@type") == "Product"
    )

    assert product_data["name"] == shop.bare.name
    assert "offers" not in product_data


# --- сужение и сортировка ---------------------------------------------


@pytest.mark.django_db
def test_a_product_without_a_price_stays_out_of_the_price_bounds(
    client: Client, shop: SimpleNamespace
) -> None:
    """Подсказки «от» и «до» считаются по товарам, у которых цена есть."""
    add_variant(shop.priced, 600, 400, shop.silver)
    third = Product.objects.create(
        category=shop.category, name="Loft", slug="loft", is_published=True
    )
    add_variant(third, 1200, 800, shop.silver)

    html = category_page(client, shop)

    assert f'placeholder="{SMALL_600_400}"' in html
    assert f'placeholder="{LARGE_1200_800}"' in html


@pytest.mark.django_db
def test_a_product_without_a_price_is_not_first_when_sorting_by_price(
    client: Client, shop: SimpleNamespace
) -> None:
    """«Дешевле» — не про то, что цена неизвестна."""
    add_variant(shop.priced, 600, 400, shop.silver)

    html = category_page(client, shop, "?sort=price")

    assert html.index(shop.priced.name) < html.index(shop.bare.name)


@pytest.mark.django_db
def test_a_product_without_a_price_is_not_first_when_sorting_by_price_desc(
    client: Client, shop: SimpleNamespace
) -> None:
    add_variant(shop.priced, 600, 400, shop.silver)

    html = category_page(client, shop, "?sort=-price")

    assert html.index(shop.priced.name) < html.index(shop.bare.name)


@pytest.mark.django_db
def test_a_product_without_a_price_drops_out_of_the_price_range(
    client: Client, shop: SimpleNamespace
) -> None:
    add_variant(shop.priced, 600, 400, shop.silver)

    html = category_page(client, shop, "?price_min=1")

    assert shop.priced.name in html
    assert shop.bare.name not in html


# --- шов --------------------------------------------------------------


@pytest.mark.django_db
def test_the_storefront_reads_the_product_price_field(
    client: Client, shop: SimpleNamespace
) -> None:
    """Витрина по-прежнему читает поле товара, а не считает на лету.

    Число вписывается мимо пересчёта: если плитка и подсказка границы
    показали именно его, значит фильтр, сортировка и разметка остались
    на том же шве — и правка цены не расползлась по проекту (ADR-0007).
    """
    add_variant(shop.priced, 600, 400, shop.silver)
    add_variant(shop.bare, 1200, 800, shop.silver)
    Product.objects.filter(pk=shop.priced.pk).update(price=SEAM_PRICE)

    html = category_page(client, shop)

    assert f"от {rub(SEAM_PRICE)} ₽" in html
    assert f'placeholder="{SEAM_PRICE}"' in html


@pytest.mark.django_db
def test_the_price_snapshot_of_an_inquiry_reads_the_same_field(
    client: Client, shop: SimpleNamespace
) -> None:
    """Снимок цены в заявке и в корзине — то же поле товара."""
    add_variant(shop.priced, 600, 400, shop.silver)
    Product.objects.filter(pk=shop.priced.pk).update(price=SEAM_PRICE)

    response = client.get(f"/api/products?ids={shop.priced.pk},{shop.bare.pk}")

    assert response.status_code == HTTPStatus.OK
    assert [item["price"] for item in response.json()["items"]] == [
        SEAM_PRICE,
        None,
    ]


# --- админка ----------------------------------------------------------


@pytest.mark.django_db
def test_owner_never_types_a_product_price(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Поля цены в форме нет, а на его месте — объяснение."""
    add_variant(shop.priced, 600, 400, shop.silver)

    html = page(
        admin_client, f"/admin/catalog/product/{shop.priced.pk}/change/"
    )

    assert 'name="price"' not in html
    assert f"{rub(SMALL_600_400)} ₽" in html
    assert "по самому дешёвому варианту" in html


@pytest.mark.django_db
def test_the_admin_explains_a_missing_price(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Пустое поле без объяснения читалось бы как «цену забыли»."""
    html = page(admin_client, f"/admin/catalog/product/{shop.bare.pk}/change/")

    assert "хотя бы один" in html


# --- пути, по которым варианты исчезают -------------------------------


@pytest.mark.django_db
def test_wiping_the_variants_at_once_leaves_the_product_without_a_price(
    shop: SimpleNamespace,
) -> None:
    """Удаление пачкой сигнал по варианту тоже шлёт."""
    add_variant(shop.priced, 600, 400, shop.silver)
    add_variant(shop.priced, 1200, 800, shop.silver)

    shop.priced.variants.all().delete()
    shop.priced.refresh_from_db()

    assert shop.priced.price is None


@pytest.mark.django_db
def test_deleting_the_product_takes_its_variants_with_it(
    shop: SimpleNamespace,
) -> None:
    """Каскад сносит варианты — сводить цену уже некому и незачем."""
    add_variant(shop.priced, 600, 400, shop.silver)

    shop.priced.delete()

    assert not ProductVariant.objects.exists()


@pytest.mark.django_db
def test_taking_a_value_off_the_dictionary_side_reaches_the_price(
    shop: SimpleNamespace,
) -> None:
    """Связь правят и со стороны справочника — товар не отстаёт.

    Без полотна остаётся изделие без единой платной статьи: ноль —
    это цена, а не её отсутствие, и товар о ней не молчит.
    """
    variant = add_variant(shop.priced, 600, 400, shop.silver)

    shop.silver.variant_selections.remove(variant)
    shop.priced.refresh_from_db()

    assert shop.priced.price == 0
    assert shop.priced.has_price
