"""Конструктор предпосчитанных вариантов в карточке товара (тикет 18).

Владелец собирает вариант, видит цену до сохранения и жмёт «Добавить».
Проверяется поведение, а не устройство: какое число он увидел, что
оказалось у заведённого варианта, что сказали правила и что стало со
списком.

Главное здесь — что показанная цена и записанная это одно число. Оно
проверяется прямо: сначала спрашивается цена собранного, потом тот же
набор сохраняется, и числа сравниваются между собой.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from http import HTTPStatus
from types import SimpleNamespace
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client

from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    PricingSettings,
    Product,
    ProductAttribute,
    ProductVariant,
)
from tests.sources import scripts_dir

# Те же условные тарифы ADR-0007, что и у остальных тестов цены:
# серебро 4 000 ₽/м², графит 5 000 ₽/м², контурная подсветка
# 2 500 ₽/пог. м
SILVER_800_600 = 9000
GRAPHITE_800_600 = 9400
BEYOND_LIMITS = 30400

# Предел производства из «Параметров расчёта»: варианты через него
# не проходят — их заводит тот, кто знает, что производство возьмёт
MAX_LONG_SIDE_MM = 3200
MAX_SHORT_SIDE_MM = 2500


@pytest.fixture
def shop(db: None) -> SimpleNamespace:
    """Зеркало с контурной подсветкой и двумя типами полотна."""
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
        order=1,
    )
    illumination = Attribute.objects.create(
        category=category, name="Подсветка", slug="podsvetka", order=1
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


def price_url(shop: SimpleNamespace) -> str:
    return f"/admin/catalog/product/{shop.product.pk}/variants/price/"


def save_url(shop: SimpleNamespace) -> str:
    return f"/admin/catalog/product/{shop.product.pk}/variants/save/"


def delete_url(shop: SimpleNamespace) -> str:
    return f"/admin/catalog/product/{shop.product.pk}/variants/delete/"


def card(client: Client, shop: SimpleNamespace) -> str:
    response = client.get(f"/admin/catalog/product/{shop.product.pk}/change/")

    assert response.status_code == HTTPStatus.OK
    return response.content.decode()


def ask_price(
    client: Client, shop: SimpleNamespace, **query: str | int
) -> dict[str, Any]:
    """Цена собранного — так её спрашивает конструктор."""
    response = client.get(price_url(shop), query)
    answer: dict[str, Any] = json.loads(response.content)
    return answer


def add(
    client: Client, shop: SimpleNamespace, **payload: object
) -> list[dict[str, Any]]:
    """«Добавить» — и список вариантов, каким он стал."""
    response = client.post(save_url(shop), payload)

    assert response.status_code == HTTPStatus.OK
    rows: list[dict[str, Any]] = json.loads(response.content)["variants"]
    return rows


# --- цена до сохранения -----------------------------------------------


@pytest.mark.django_db
def test_the_price_is_named_before_anything_is_saved(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Ради этого конструктор и заведён: число видно до «Добавить»."""
    answer = ask_price(
        admin_client,
        shop,
        width_mm=800,
        height_mm=600,
        values=shop.silver.pk,
    )

    assert answer["price"] == SILVER_800_600
    assert not ProductVariant.objects.exists()


@pytest.mark.django_db
def test_the_shown_price_is_the_one_the_variant_gets(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Показанное и записанное — одно число, а не два похожих.

    Разойдись они, владелец добавлял бы вариант, увидев одну цену,
    а в списке находил другую — и не поверил бы больше ни одной.
    """
    shown = ask_price(
        admin_client,
        shop,
        width_mm=800,
        height_mm=600,
        values=shop.graphite.pk,
    )["price"]

    add(
        admin_client,
        shop,
        width_mm=800,
        height_mm=600,
        values=[shop.graphite.pk],
    )

    assert shown == GRAPHITE_800_600
    assert ProductVariant.objects.get().price == shown


@pytest.mark.django_db
def test_a_tariff_change_reaches_the_price_before_saving(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Конструктор считает по справочнику, а не по памяти о нём."""
    shop.silver.rate = Decimal(8000)
    shop.silver.save()

    answer = ask_price(
        admin_client,
        shop,
        width_mm=800,
        height_mm=600,
        values=shop.silver.pk,
    )

    assert answer["price"] > SILVER_800_600


@pytest.mark.django_db
def test_a_size_beyond_production_still_gets_a_price(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Варианты владельца идут мимо предела производства.

    Покупателю на таком размере сайт цены не называет — это личное
    пожелание. Владелец же заводит вариант, зная, что производство
    возьмёт (CONTEXT.md), и молчание было бы отказом ему в том, что
    он умеет сам.
    """
    PricingSettings.objects.create(
        max_long_side_mm=MAX_LONG_SIDE_MM,
        max_short_side_mm=MAX_SHORT_SIDE_MM,
    )

    answer = ask_price(
        admin_client,
        shop,
        width_mm=MAX_LONG_SIDE_MM + 500,
        height_mm=600,
        values=shop.silver.pk,
    )

    assert answer["price"] == BEYOND_LIMITS


@pytest.mark.django_db
def test_a_size_that_is_not_a_size_is_refused_in_words(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Пустое поле — не нулевое зеркало, и молчать о нём нельзя."""
    response = admin_client.get(price_url(shop), {"width_mm": "600"})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "миллиметрах" in json.loads(response.content)["error"]


# --- заведение и правка -----------------------------------------------


@pytest.mark.django_db
def test_adding_creates_the_variant_and_prices_the_product(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """«Добавить» заводит вариант, и товар получает своё «от X ₽»."""
    rows = add(
        admin_client,
        shop,
        width_mm=800,
        height_mm=600,
        values=[shop.silver.pk],
    )

    variant = ProductVariant.objects.get()
    shop.product.refresh_from_db()
    assert variant.size_label == "800 × 600 мм"
    assert list(variant.values.all()) == [shop.silver]
    assert shop.product.price == SILVER_800_600
    assert [row["price"] for row in rows] == [SILVER_800_600]


@pytest.mark.django_db
def test_editing_rewrites_the_variant_instead_of_adding_a_second(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Правка — это тот же вариант с другими числами."""
    rows = add(
        admin_client,
        shop,
        width_mm=800,
        height_mm=600,
        values=[shop.silver.pk],
    )

    rows = add(
        admin_client,
        shop,
        variant=rows[0]["variant_id"],
        width_mm=800,
        height_mm=600,
        values=[shop.graphite.pk],
    )

    variant = ProductVariant.objects.get()
    assert len(rows) == 1
    assert list(variant.values.all()) == [shop.graphite]
    assert variant.price == GRAPHITE_800_600


@pytest.mark.django_db
def test_a_deleted_variant_leaves_the_product_without_a_price(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Удаление доезжает и до цены товара: она берётся по вариантам."""
    rows = add(
        admin_client,
        shop,
        width_mm=800,
        height_mm=600,
        values=[shop.silver.pk],
    )

    response = admin_client.post(
        delete_url(shop), {"variant": rows[0]["variant_id"]}
    )

    shop.product.refresh_from_db()
    assert response.status_code == HTTPStatus.OK
    assert json.loads(response.content)["variants"] == []
    assert not ProductVariant.objects.exists()
    assert shop.product.price is None


@pytest.mark.django_db
def test_the_price_is_never_typed_by_hand(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Присланная цена не становится ценой: её считает движок."""
    add(
        admin_client,
        shop,
        width_mm=800,
        height_mm=600,
        values=[shop.silver.pk],
        price="1",
    )

    assert ProductVariant.objects.get().price == SILVER_800_600


@pytest.mark.django_db
def test_the_cheapest_variant_is_the_one_marked(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Видно, какой вариант даёт товару его «от X ₽»."""
    add(
        admin_client,
        shop,
        width_mm=800,
        height_mm=600,
        values=[shop.graphite.pk],
    )
    rows = add(
        admin_client,
        shop,
        width_mm=800,
        height_mm=600,
        values=[shop.silver.pk],
    )

    shop.product.refresh_from_db()
    marked = [row for row in rows if row["sets_product_price"]]
    assert [row["price"] for row in marked] == [shop.product.price]


@pytest.mark.django_db
def test_the_owner_still_orders_the_variants(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Порядок вариантов задаёт владелец, и конструктор его не отнял.

    Не косметика: в этом порядке варианты стоят на карточке, и на
    первом подходящем открывается калькулятор покупателя. Инлайн,
    который конструктор заменил, это поле показывал — потеряв его,
    владелец лишился бы выбора стартового размера.
    """
    add(
        admin_client,
        shop,
        width_mm=800,
        height_mm=600,
        values=[shop.silver.pk],
        order=2,
    )
    rows = add(
        admin_client,
        shop,
        width_mm=900,
        height_mm=600,
        values=[shop.silver.pk],
        order=1,
    )

    assert [row["order"] for row in rows] == [1, 2]
    assert [row["size_label"] for row in rows] == [
        "900 × 600 мм",
        "800 × 600 мм",
    ]


# --- правила сборки ---------------------------------------------------


@pytest.mark.django_db
def test_two_values_of_one_attribute_are_rejected(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Серебро и графит сразу — это два варианта, а не один."""
    response = admin_client.post(
        save_url(shop),
        {
            "width_mm": 800,
            "height_mm": 600,
            "values": [shop.silver.pk, shop.graphite.pk],
        },
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "Тип полотна" in json.loads(response.content)["error"]
    assert not ProductVariant.objects.exists()


@pytest.mark.django_db
def test_a_value_that_left_the_dictionary_is_refused(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Значение исчезло, пока владелец собирал, — сохранять нечего.

    Молча пропустив его, конструктор завёл бы вариант, отличающийся
    от того, что владелец видел на экране.
    """
    gone = shop.graphite.pk
    shop.graphite.delete()

    response = admin_client.post(
        save_url(shop),
        {"width_mm": 800, "height_mm": 600, "values": [gone]},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "справочнике" in json.loads(response.content)["error"]
    assert not ProductVariant.objects.exists()


@pytest.mark.django_db
def test_a_negative_order_is_refused_instead_of_silently_zeroed(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Минус в порядке — не ноль, а промах: о нём говорят вслух.

    Подменив его нулём, конструктор поставил бы вариант не туда, куда
    владелец целился, и не сказал бы об этом.
    """
    response = admin_client.post(
        save_url(shop),
        {"width_mm": 800, "height_mm": 600, "order": -1},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "Порядок" in json.loads(response.content)["error"]
    assert not ProductVariant.objects.exists()


@pytest.mark.django_db
def test_editing_a_variant_that_is_already_gone_says_so(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Вариант удалили в другой вкладке — правка не заводит новый."""
    variant = ProductVariant.objects.create(
        product=shop.product, width_mm=800, height_mm=600
    )
    lost = variant.pk
    variant.delete()

    response = admin_client.post(
        save_url(shop),
        {"variant": lost, "width_mm": 900, "height_mm": 600},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert not ProductVariant.objects.exists()


@pytest.mark.django_db
def test_a_value_of_a_foreign_category_is_rejected(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Вариант зеркала не собрать из атрибутов душевых перегородок."""
    other = Category.objects.create(name="Перегородки", slug="peregorodki")
    glass = Attribute.objects.create(
        category=other, name="Стекло", slug="steklo"
    )
    matte = AttributeValue.objects.create(attribute=glass, value="Матовое")

    response = admin_client.post(
        save_url(shop),
        {"width_mm": 800, "height_mm": 600, "values": [matte.pk]},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "Стекло" in json.loads(response.content)["error"]
    assert not ProductVariant.objects.exists()


@pytest.mark.django_db
def test_a_variant_of_another_product_is_not_touched(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Конструктор правит варианты своего товара и ничьи больше."""
    stranger = Product.objects.create(
        category=shop.category, name="Луна", slug="luna"
    )
    variant = ProductVariant.objects.create(
        product=stranger, width_mm=800, height_mm=600
    )

    response = admin_client.post(delete_url(shop), {"variant": variant.pk})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert ProductVariant.objects.filter(pk=variant.pk).exists()


# --- сама карточка ----------------------------------------------------


@pytest.mark.django_db
def test_the_builder_lives_inside_the_product_card(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Значения разложены по атрибутам, чужой категории в них нет."""
    other = Category.objects.create(name="Перегородки", slug="peregorodki")
    profile = Attribute.objects.create(
        category=other, name="Профиль", slug="profil"
    )
    AttributeValue.objects.create(attribute=profile, value="Хром")

    page = card(admin_client, shop)

    assert "<legend>Тип полотна</legend>" in page
    assert f'data-variant-value value="{shop.silver.pk}"' in page
    assert "<legend>Профиль</legend>" not in page


@pytest.mark.django_db
def test_the_builder_is_not_a_form_inside_a_form(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Вложенную форму браузер выбрасывает — и конструктора нет вовсе.

    Django печатает конструктор внутри формы товара, и ошибка эта
    невидима серверу: разметка отдаётся целиком, а разбирает её
    браузер. Проверяется поэтому сама разметка.

    Имён у полей панели нет по той же причине с другой стороны: с
    именами они уезжали бы на сервер при сохранении карточки товара.
    """
    page = card(admin_client, shop)
    builder = page[
        page.index('id="variant-builder"') : page.index('id="variant-empty"')
    ]

    assert "<form" not in builder
    assert 'type="submit"' not in builder


@pytest.mark.django_db
def test_the_builder_explains_that_an_empty_choice_is_normal(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Пустой набор флажков — норма, и сказать об этом больше негде.

    В списке вариантов подписи нет: не отмеченный ни один флажок там
    неотличим от недозаполненной строки.
    """
    page = card(admin_client, shop)

    assert "берёт значения товара целиком" in page
    assert "заменяет умолчание товара" in page


@pytest.mark.django_db
def test_a_reader_of_the_card_gets_no_builder(
    client: Client, shop: SimpleNamespace
) -> None:
    """Кто карточку только смотрит, тот не получает и конструктора.

    Адреса конструктора спрашивают право на правку, и нарисованные
    такому пользователю поля были бы предложением заведомо
    отвергаемого.
    """
    reader = get_user_model().objects.create_user(
        username="reader", password="reader-password", is_staff=True
    )
    reader.user_permissions.add(
        Permission.objects.get(codename="view_product")
    )

    assert client.login(username="reader", password="reader-password")
    page = client.get(
        f"/admin/catalog/product/{shop.product.pk}/change/"
    ).content.decode()

    assert 'id="variant-builder-form"' not in page


@pytest.mark.django_db
def test_a_product_that_is_not_saved_yet_has_no_builder(
    admin_client: Client, db: None
) -> None:
    """Вариант без товара не существует — и конструктора там нет."""
    page = admin_client.get("/admin/catalog/product/add/").content.decode()

    assert "Сначала сохраните товар" in page
    assert 'id="variant-builder-form"' not in page


@pytest.mark.django_db
def test_the_card_never_offers_a_price_field(
    admin_client: Client, shop: SimpleNamespace
) -> None:
    """Второй правды о цене у товара нет — вводить её негде."""
    page = card(admin_client, shop)

    assert 'name="price"' not in page


@pytest.mark.django_db
def test_a_stranger_gets_nothing_from_the_builder(
    client: Client, shop: SimpleNamespace
) -> None:
    """Адреса конструктора — часть админки, и доступ у них её."""
    response = client.post(save_url(shop), {"width_mm": 800, "height_mm": 600})

    assert response.status_code == HTTPStatus.FOUND
    assert "/admin/login/" in response["Location"]
    assert not ProductVariant.objects.exists()


# Сам вызов, а не слово: упомянуть `DOMContentLoaded` в комментарии
# над кодом, который его не ждёт, — ровно та ошибка, которую тест ловит
WAITS_FOR_MARKUP = re.compile(
    r"""addEventListener\(\s*["']DOMContentLoaded["']"""
)


def test_admin_scripts_wait_for_the_markup() -> None:
    """Скрипт админки обязан дождаться разметки — иначе он мёртв.

    Медиа `ModelAdmin` печатается в `<head>` и без `defer`: скрипт
    отрабатывает раньше, чем появляется то, к чему он цепляется, и
    молча ничего не делает. Серверу эта поломка невидима — разметка
    отдаётся полной, — а тесты по отданному HTML её не ловят: страница
    целиком на месте. Витрина от этого защищена `defer` в шаблонах,
    у админки такого места нет, и остаётся сам скрипт.
    """
    scripts = sorted(scripts_dir().glob("admin-*.js"))
    assert scripts, "скриптов админки не нашлось — тест смотрит не туда"

    hasty = [
        path.name
        for path in scripts
        if not WAITS_FOR_MARKUP.search(path.read_text(encoding="utf-8"))
    ]

    assert not hasty, (
        "скрипт админки цепляется к разметке, которой ещё нет; "
        "оберните запуск в DOMContentLoaded: " + ", ".join(hasty)
    )
