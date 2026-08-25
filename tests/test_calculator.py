"""Калькулятор в карточке (тикет 20): кому он достаётся и из чего собран.

Проверяется отданный сервером HTML и общий с эндпоинтом гейт. Сам
пересчёт делает браузер, и тестами он не покрывается — как и остальной
JS проекта (спека расчёта, «что тестами не покрывается»); проверяется
серверный контракт, на котором он стоит.
"""

from __future__ import annotations

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
    PricingSettings,
    Product,
    ProductAttribute,
    ProductVariant,
)

# Условные тарифы ADR-0007
GLASS_RATE = Decimal(4000)
CONTOUR_RATE = Decimal(2500)
HEATING_RATE = Decimal(3500)

# Блок калькулятора и его органы управления в разметке
CALC = re.compile(r"<div class=\"calc\"[^>]*data-calc\b")
SELECT_LABEL = re.compile(
    r"<span>([^<]+)</span>\s*<select data-calc-value>", re.DOTALL
)
# Дисклеймер стоит после результата расчёта, а не где-то на странице
NOTE_UNDER_RESULT = re.compile(
    r"data-calc-result.*?</div>\s*</div>\s*<p class=\"offer-note\"", re.DOTALL
)


@pytest.fixture
def shop(db: None) -> SimpleNamespace:
    """Зеркало с подсветкой: полотно и подогрев меняет покупатель.

    Подсветка описывает модель — в калькуляторе её не крутят, но
    в расчёт она входит: считается от периметра.
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
        rate=GLASS_RATE,
        scaled_by_shape=True,
    )
    AttributeValue.objects.create(
        attribute=blade,
        value="Графит",
        unit=AttributeValue.Unit.SQUARE_METER,
        rate=Decimal(5000),
        scaled_by_shape=True,
        order=1,
    )
    heating_attribute = Attribute.objects.create(
        category=category,
        name="Подогрев",
        slug="podogrev",
        is_customer_editable=True,
        order=1,
    )
    heating = AttributeValue.objects.create(
        attribute=heating_attribute,
        value="Есть",
        unit=AttributeValue.Unit.PIECE,
        rate=HEATING_RATE,
    )
    no_heating = AttributeValue.objects.create(
        attribute=heating_attribute, value="Нет", order=1
    )
    illumination = Attribute.objects.create(
        category=category,
        name="Подсветка",
        slug="podsvetka",
        order=2,
    )
    contour = AttributeValue.objects.create(
        attribute=illumination,
        value="Контурная",
        unit=AttributeValue.Unit.LINEAR_METER,
        rate=CONTOUR_RATE,
    )
    product = Product.objects.create(
        category=category,
        name="Halo Moon",
        slug="halo-moon",
        is_published=True,
    )
    ProductAttribute.objects.create(
        product=product, attribute=blade, value_option=silver
    )
    ProductAttribute.objects.create(
        product=product, attribute=heating_attribute, value_option=no_heating
    )
    ProductAttribute.objects.create(
        product=product, attribute=illumination, value_option=contour
    )
    return SimpleNamespace(
        category=category,
        product=product,
        blade=blade,
        silver=silver,
        heating=heating,
        heating_attribute=heating_attribute,
        illumination=illumination,
        contour=contour,
    )


def card(client: Client, product: Product) -> str:
    response = client.get(product_url(product))
    assert response.status_code == HTTPStatus.OK
    return response.content.decode()


def product_url(product: Product) -> str:
    return f"/catalog/{product.category.slug}/{product.slug}/"


def test_a_product_inside_the_calculable_set_gets_the_calculator(
    client: Client, shop: SimpleNamespace
) -> None:
    """Изделие, описанное целиком и с тарифами, считается на карточке."""
    assert CALC.search(card(client, shop.product))


def test_the_calculator_offers_only_what_the_buyer_changes(
    client: Client, shop: SimpleNamespace
) -> None:
    """Полотно и подогрев покупатель крутит, подсветку — нет.

    За другой подсветкой, рамой или формой он идёт в другой товар:
    это свойства модели, а не настройки изделия (CONTEXT.md).
    """
    labels = SELECT_LABEL.findall(card(client, shop.product))

    assert labels == ["Тип полотна", "Подогрев"]


def test_the_calculator_starts_from_the_typical_size(
    client: Client, shop: SimpleNamespace
) -> None:
    """Поля размера открываются на первом варианте владельца."""
    ProductVariant.objects.create(
        product=shop.product, width_mm=800, height_mm=600
    )

    body = card(client, shop.product)

    assert 'value="800" data-calc-width' in body
    assert 'value="600" data-calc-height' in body


def test_the_calculator_opens_on_the_whole_variant(
    client: Client, shop: SimpleNamespace
) -> None:
    """Вариант открывается целиком: и размером, и своими значениями.

    Возьми калькулятор у варианта один размер, на тех же параметрах он
    назвал бы не ту цену, что стоит в строке таблицы, — и объяснить
    расхождение покупателю было бы нечем (ADR-0007).
    """
    variant = ProductVariant.objects.create(
        product=shop.product, width_mm=800, height_mm=600
    )
    variant.values.add(shop.heating)

    body = card(client, shop.product)

    assert f'<option value="{shop.heating.pk}" selected>Есть' in body


def test_a_variant_the_calculator_cannot_show_does_not_open_it(
    client: Client, shop: SimpleNamespace
) -> None:
    """Вариант с другой подсветкой калькулятор воспроизвести не может.

    Списка подсветок у него нет: открывшись на размере такого варианта,
    он посчитал бы изделие с подсветкой товара — не то, что в строке.
    """
    front = AttributeValue.objects.create(
        attribute=shop.illumination,
        value="Фронтальная",
        unit=AttributeValue.Unit.SQUARE_METER,
        rate=Decimal(6000),
        order=1,
    )
    variant = ProductVariant.objects.create(
        product=shop.product, width_mm=800, height_mm=600
    )
    variant.values.add(front)

    body = card(client, shop.product)

    assert 'value="" data-calc-width' in body


def test_the_default_of_the_product_is_the_selected_option(
    client: Client, shop: SimpleNamespace
) -> None:
    """Список открывается на том, что у товара стоит по умолчанию."""
    body = card(client, shop.product)

    assert f'<option value="{shop.silver.pk}" selected>Серебро' in body


def test_a_product_with_an_unfilled_attribute_has_no_calculator(
    client: Client, shop: SimpleNamespace
) -> None:
    """Товар, у которого атрибут не заведён, описан не целиком.

    Считать его — значит считать изделие, о котором сайт знает не всё.
    """
    bare = Product.objects.create(
        category=shop.category,
        name="Без подсветки",
        slug="bez-podsvetki",
        is_published=True,
    )
    ProductAttribute.objects.create(
        product=bare, attribute=shop.blade, value_option=shop.silver
    )

    assert not CALC.search(card(client, bare))


def test_the_calculator_carries_the_address_of_the_inquiry(
    client: Client, shop: SimpleNamespace
) -> None:
    """Некуда посчитать — калькулятор зовёт к подборке, и адрес не выдуман.

    Ссылку рисует `product.js` по этому атрибуту: пропадёт он —
    «Перейти к заявке →» уедет в никуда, и молча (тикет 07).
    """
    assert 'data-calc-inquiry-url="/cart/"' in card(client, shop.product)


def test_a_product_outside_the_set_still_shows_variants_and_a_way_to_ask(
    client: Client, shop: SimpleNamespace
) -> None:
    """Вне считаемого набора карточка живёт вариантами и подборкой.

    Формы заявки на карточке больше нет (тикет 07): к менеджеру ведёт
    та же кнопка, что и у считаемого товара.
    """
    shop.blade.is_customer_editable = False
    shop.blade.save()
    outside = Product.objects.create(
        category=shop.category,
        name="Багетное",
        slug="bagetnoe",
        is_published=True,
    )
    ProductVariant.objects.create(product=outside, width_mm=800, height_mm=600)

    body = card(client, outside)

    assert not CALC.search(body)
    assert "Типовые размеры" in body
    assert 'data-toggle="cart"' in body


def test_a_product_without_a_single_tariff_has_no_calculator(
    client: Client, shop: SimpleNamespace
) -> None:
    """Изделию без единой платной статьи считать нечего.

    Итогом был бы ноль или минимальная сумма заказа — число, за
    которым ничего не стоит.
    """
    untariffed = Product.objects.create(
        category=shop.category,
        name="Без тарифов",
        slug="bez-tarifov",
        is_published=True,
    )
    free = {
        shop.blade: "Бронза",
        shop.heating_attribute: "Нет тоже",
        shop.illumination: "Нет",
    }
    for attribute, value in free.items():
        ProductAttribute.objects.create(
            product=untariffed,
            attribute=attribute,
            value_option=AttributeValue.objects.create(
                attribute=attribute, value=value, order=9
            ),
        )

    assert not CALC.search(card(client, untariffed))


def test_a_variant_beyond_production_does_not_open_the_calculator(
    client: Client, shop: SimpleNamespace
) -> None:
    """Вариант владельца через предел не проходит, а калькулятор — да.

    Открывшись на его размере, калькулятор позвал бы оставить заявку
    там, где в строке таблицы стоит настоящая цена.
    """
    PricingSettings.objects.create(
        max_long_side_mm=2000, max_short_side_mm=1500
    )
    ProductVariant.objects.create(
        product=shop.product, width_mm=2400, height_mm=1000
    )
    ProductVariant.objects.create(
        product=shop.product, width_mm=800, height_mm=600, order=1
    )

    body = card(client, shop.product)

    assert 'value="800" data-calc-width' in body


def test_an_unfilled_attribute_without_a_tariff_keeps_the_calculator(
    client: Client, shop: SimpleNamespace
) -> None:
    """Незаполненный «вес» цену не укорачивает — молчать о ней незачем.

    Тариф живёт у значения справочника, а у «да/нет» и числовых
    значения справочника нет: в расчёт они не входят вовсе.
    """
    Attribute.objects.create(
        category=shop.category,
        name="Вес",
        slug="ves",
        kind=Attribute.Kind.NUMBER,
        order=3,
    )

    assert CALC.search(card(client, shop.product))


def test_a_free_choice_leaves_nothing_to_charge_and_is_refused(
    client: Client, shop: SimpleNamespace
) -> None:
    """Выбор без тарифа способен обнулить единственную платную статью.

    Гейт товара смотрит на его умолчания; полотно без тарифа вместо
    тарифицированного оставляет изделие без единой статьи, и итогом
    стал бы ноль или минимальная сумма заказа.
    """
    bare = Product.objects.create(
        category=shop.category,
        name="Только полотно",
        slug="tolko-polotno",
        is_published=True,
    )
    free_blade = AttributeValue.objects.create(
        attribute=shop.blade, value="Бронза", order=2
    )
    ProductAttribute.objects.create(
        product=bare, attribute=shop.blade, value_option=shop.silver
    )
    for attribute in (shop.heating_attribute, shop.illumination):
        ProductAttribute.objects.create(
            product=bare,
            attribute=attribute,
            value_option=AttributeValue.objects.create(
                attribute=attribute, value="Нет вовсе", order=9
            ),
        )

    assert CALC.search(card(client, bare))
    response = client.get(
        "/api/price",
        {
            "product": str(bare.pk),
            "width_mm": "800",
            "height_mm": "600",
            "values": str(free_blade.pk),
        },
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_the_disclaimer_stands_under_every_price(
    client: Client, shop: SimpleNamespace
) -> None:
    """У карточки без калькулятора дисклеймер всё равно печатается.

    Экземпляр он один и стоит после всего, что называет цену: снимать
    текст о ценах — решение юридическое, не витринное.
    """
    shop.blade.is_customer_editable = False
    shop.blade.save()
    outside = Product.objects.create(
        category=shop.category,
        name="Багетное",
        slug="bagetnoe",
        is_published=True,
    )

    body = card(client, outside)

    assert not CALC.search(body)
    assert body.count('<p class="offer-note">') == 1


def test_the_disclaimer_stands_under_the_result(
    client: Client, shop: SimpleNamespace
) -> None:
    """«Расчёт не является публичной офертой» — рядом с числом."""
    assert NOTE_UNDER_RESULT.search(card(client, shop.product))


def test_the_endpoint_refuses_what_the_card_does_not_offer(
    client: Client, shop: SimpleNamespace
) -> None:
    """Гейт один: адрес расчёта открыт, и обойти карточку им нельзя."""
    bare = Product.objects.create(
        category=shop.category,
        name="Без подсветки",
        slug="bez-podsvetki",
        is_published=True,
    )
    ProductAttribute.objects.create(
        product=bare, attribute=shop.blade, value_option=shop.silver
    )

    response = client.get(
        "/api/price",
        {"product": bare.pk, "width_mm": 800, "height_mm": 600},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_a_hidden_price_leaves_the_calculator_in_place(
    client: Client, shop: SimpleNamespace
) -> None:
    """Признак товара гасит цену, а не конструктор (тикет 16, ADR-0008).

    Поля размеров и списки значений остаются рабочими: погашенная цена
    отбирает у покупателя число, а не способ сказать, чего он хочет.
    """
    shop.product.hides_calculated_price = True
    shop.product.save()

    body = card(client, shop.product)

    assert CALC.search(body)
    assert "data-calc-width" in body
    assert "Тип полотна" in {
        name.strip() for name in SELECT_LABEL.findall(body)
    }


def test_a_hidden_price_says_who_names_it(
    client: Client, shop: SimpleNamespace
) -> None:
    """На месте цены — строка о менеджере, а не пустой блок.

    Молчащий блок покупатель прочитал бы как сломанную страницу.
    Печатает строку сервер: за числом браузеру ходить незачем, и
    место под ответ эндпоинта карточка не оставляет.
    """
    shop.product.hides_calculated_price = True
    shop.product.save()

    body = card(client, shop.product)

    assert "data-calc-priced" not in body
    assert "data-calc-result" not in body
    assert "Цену этого зеркала называет менеджер" in body


def test_the_endpoint_names_no_price_where_the_card_is_silent(
    client: Client, shop: SimpleNamespace
) -> None:
    """Гейт цены один: адрес расчёта открыт, и обойти карточку им нельзя.

    Ни итога, ни доплат: доплаты — такие же рубли, и по ним цена
    восстанавливалась бы обратно.
    """
    shop.product.hides_calculated_price = True
    shop.product.save()

    response = client.get(
        "/api/price",
        {
            "product": shop.product.pk,
            "width_mm": 800,
            "height_mm": 600,
            "values": str(shop.heating.pk),
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "total": None,
        "additions": [],
        "needs_inquiry": True,
    }


def test_a_hidden_price_does_not_touch_the_variants(
    client: Client, shop: SimpleNamespace
) -> None:
    """Предпосчитанные варианты признак не гасит (ADR-0008).

    Их цены заводит владелец — тот, кто и решает, за сколько продаёт;
    гейт расчёта о них не спрашивают ни каталог, ни карточка.
    """
    shop.product.hides_calculated_price = True
    shop.product.save()
    ProductVariant.objects.create(
        product=shop.product, width_mm=800, height_mm=600
    )
    shop.product.refresh_from_db()

    body = card(client, shop.product)

    assert shop.product.price is not None
    assert "Типовые размеры" in body


def test_a_hidden_price_keeps_the_price_from_in_the_catalogue(
    client: Client, shop: SimpleNamespace
) -> None:
    """«От X ₽» в каталоге стоит на вариантах, а не на расчёте.

    Признак гасит цену, которую называет сайт; цену, которую назвал
    владелец, он не трогает — иначе товар пропал бы и из сужения по
    диапазону цены, и из сортировки (ADR-0008).
    """
    shop.product.hides_calculated_price = True
    shop.product.save()
    ProductVariant.objects.create(
        product=shop.product, width_mm=800, height_mm=600
    )
    shop.product.refresh_from_db()

    listing = client.get(f"/catalog/{shop.category.slug}/")

    assert listing.status_code == HTTPStatus.OK
    assert rub(shop.product.price) in listing.content.decode()
