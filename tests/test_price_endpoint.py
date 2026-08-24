"""Эндпоинт расчёта (тикет 19): итог, подписи добавок и отказы.

Проверяется отданное наружу, а не устройство расчёта: какое число
вернулось, что попало в подписи и — отдельно — чего в теле ответа нет
ни при каких условиях. Секретность тарифов здесь не обещание, а тест.
"""

from __future__ import annotations

import json
from decimal import Decimal
from http import HTTPStatus
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from django.test import Client

from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    PricingSettings,
    Product,
    ProductAttribute,
)

if TYPE_CHECKING:
    from django.test.client import (
        _MonkeyPatchedWSGIResponse as TestResponse,
    )

# Условные тарифы ADR-0007: полотно 4 000 ₽/м², графит 5 000 ₽/м²,
# контурная подсветка 2 500 ₽/пог. м, подогрев 3 500 ₽/шт
GLASS_RATE = Decimal(4000)
GRAPHITE_RATE = Decimal(5000)
CONTOUR_RATE = Decimal(2500)
HEATING_RATE = Decimal(3500)

# Зеркало 800 × 600: 0,48 м² и 2,8 пог. м; итог округляется до сотни
SILVER_WITH_CONTOUR = 9000
GRAPHITE_WITH_CONTOUR = 9400
WITH_HEATING = 12500
# Доплата — разница с тем же изделием без этого выбора, а не цена
# статьи: графит стоит 2 400 ₽ против 1 920 ₽ серебра у товара
GRAPHITE_SURCHARGE = 400
HEATING_SURCHARGE = 3500

# Чего в ответе быть не должно: ставки справочника, стоимости статей,
# из которых ставка делится обратно на известном размере, единицы
# расхода и коэффициент формы. Штучной ставки в списке нет намеренно —
# у выбранной добавки «за штуку» доплата и есть её ставка, и спрятать
# одно от другого нельзя, не спрятав саму подпись (ADR-0007)
SECRETS = (
    "4000",
    "5000",
    "2500",
    "2400",
    "7000",
    "square_meter",
    "linear_meter",
    "rate",
    "unit",
    "scaled_by_shape",
)


@pytest.fixture
def shop(db: None) -> SimpleNamespace:
    """Зеркало с контурной подсветкой: полотно и подогрев меняет покупатель."""
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
    graphite = AttributeValue.objects.create(
        attribute=blade,
        value="Графит",
        unit=AttributeValue.Unit.SQUARE_METER,
        rate=GRAPHITE_RATE,
        scaled_by_shape=True,
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
        product=product, attribute=illumination, value_option=contour
    )
    return SimpleNamespace(
        category=category,
        product=product,
        blade=blade,
        silver=silver,
        graphite=graphite,
        heating=heating,
        illumination=illumination,
        contour=contour,
    )


def ask(
    client: Client,
    shop: SimpleNamespace,
    *,
    width_mm: int = 800,
    height_mm: int = 600,
    values: str = "",
) -> TestResponse:
    return client.get(
        "/api/price",
        {
            "product": shop.product.pk,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "values": values,
        },
    )


def test_a_configuration_gets_its_total(
    client: Client, shop: SimpleNamespace
) -> None:
    """Валидный запрос возвращает итог по умолчаниям товара."""
    response = ask(client, shop)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "total": SILVER_WITH_CONTOUR,
        "additions": [],
        "needs_inquiry": False,
    }


def test_the_choice_of_the_buyer_changes_the_total(
    client: Client, shop: SimpleNamespace
) -> None:
    """Выбранное полотно перекрывает умолчание товара, а не прибавляется."""
    response = ask(client, shop, values=str(shop.graphite.pk))

    assert response.json()["total"] == GRAPHITE_WITH_CONTOUR


def test_the_buyer_sees_what_the_addition_costs(
    client: Client, shop: SimpleNamespace
) -> None:
    """Подпись выбранной добавки приходит с её ценой."""
    response = ask(client, shop, values=str(shop.heating.pk))

    body = response.json()
    assert body["total"] == WITH_HEATING
    assert body["additions"] == [
        {"label": "Подогрев: Есть", "amount": HEATING_SURCHARGE}
    ]


def test_a_surcharge_is_the_difference_and_not_the_cost_of_the_line(
    client: Client, shop: SimpleNamespace
) -> None:
    """Графит доплачивается разницей с полотном товара, а не целиком.

    Стоимость статьи при известном размере — это ставка за квадрат;
    разница двух ставок ею не является. Здесь и проходит граница
    между «за что доплата» и «из чего сложена цена» (ADR-0007).
    """
    response = ask(client, shop, values=str(shop.graphite.pk))

    assert response.json()["additions"] == [
        {"label": "Тип полотна: Графит", "amount": GRAPHITE_SURCHARGE}
    ]


def test_a_choice_that_changes_nothing_says_nothing(
    client: Client, shop: SimpleNamespace
) -> None:
    """Выбор, совпавший с умолчанием товара, доплаты не рождает."""
    response = ask(client, shop, values=str(shop.silver.pk))

    assert response.json() == {
        "total": SILVER_WITH_CONTOUR,
        "additions": [],
        "needs_inquiry": False,
    }


def test_a_product_without_a_single_tariff_is_not_priced(
    client: Client, shop: SimpleNamespace
) -> None:
    """Изделие, у которого не набралось ни статьи, цены не получает.

    Итог был бы нулём или минимальной суммой заказа — числом, за
    которым ничего не стоит; заявка честнее.
    """
    bare = Product.objects.create(
        category=shop.category,
        name="Без тарифов",
        slug="bez-tarifov",
        is_published=True,
    )

    response = client.get(
        "/api/price",
        {"product": bare.pk, "width_mm": 800, "height_mm": 600},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_what_the_product_carries_stays_inside_the_total(
    client: Client, shop: SimpleNamespace
) -> None:
    """Подсветка товара покупателем не выбрана — своей строки у неё нет.

    Строкой отвечает лишь выбранное: иначе ответ разложил бы изделие
    на статьи, из которых видно устройство наценки.
    """
    response = ask(client, shop, values=str(shop.heating.pk))

    labels = [item["label"] for item in response.json()["additions"]]
    assert "Подсветка: Контурная" not in labels


def test_no_tariff_from_the_dictionary_reaches_the_body(
    client: Client, shop: SimpleNamespace
) -> None:
    """Ставок, единиц расхода и коэффициентов в ответе нет."""
    response = ask(
        client, shop, values=f"{shop.graphite.pk},{shop.heating.pk}"
    )

    body = json.dumps(response.json(), ensure_ascii=False)
    for secret in SECRETS:
        assert secret not in body


def test_a_size_beyond_production_invites_an_inquiry(
    client: Client, shop: SimpleNamespace
) -> None:
    """За пределом отдаётся признак «нужна заявка», а не цена и не ошибка."""
    PricingSettings.objects.create(
        max_long_side_mm=2000, max_short_side_mm=1500
    )

    response = ask(client, shop, width_mm=2400, height_mm=1000)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "total": None,
        "additions": [],
        "needs_inquiry": True,
    }


def test_a_rotated_size_within_production_still_gets_a_price(
    client: Client, shop: SimpleNamespace
) -> None:
    """Зеркало поворачивают: 1900 × 400 ложится в тот же предел."""
    PricingSettings.objects.create(
        max_long_side_mm=2000, max_short_side_mm=1500
    )

    response = ask(client, shop, width_mm=1900, height_mm=400)

    assert response.json()["needs_inquiry"] is False
    assert response.json()["total"] is not None


@pytest.mark.parametrize(
    "invalid",
    [
        {"width_mm": 0},
        {"height_mm": 0},
        {"width_mm": -600},
        {"values": "серебро"},
    ],
)
def test_a_malformed_request_is_rejected(
    client: Client, shop: SimpleNamespace, invalid: dict[str, object]
) -> None:
    """Мусор во входе отвергается разбором, а не считается."""
    response = ask(client, shop, **invalid)  # type: ignore[arg-type]

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_a_product_out_of_the_catalogue_is_rejected(
    client: Client, shop: SimpleNamespace
) -> None:
    """Снятый с публикации товар цены не считает."""
    shop.product.is_published = False
    shop.product.save()

    response = ask(client, shop)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_an_unknown_value_is_rejected(
    client: Client, shop: SimpleNamespace
) -> None:
    """Значения, которого в справочнике нет, расчёт не пропускает."""
    response = ask(client, shop, values=str(shop.heating.pk + 1000))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_a_value_the_buyer_does_not_choose_is_rejected(
    client: Client, shop: SimpleNamespace
) -> None:
    """Подсветку покупатель не меняет — прислать её значение нельзя."""
    response = ask(client, shop, values=str(shop.contour.pk))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_a_value_of_another_category_is_rejected(
    client: Client, shop: SimpleNamespace
) -> None:
    """Значение чужой категории к этому товару отношения не имеет."""
    other = Category.objects.create(name="Перегородки", slug="peregorodki")
    attribute = Attribute.objects.create(
        category=other,
        name="Профиль",
        slug="profil",
        is_customer_editable=True,
    )
    alien = AttributeValue.objects.create(attribute=attribute, value="Чёрный")

    response = ask(client, shop, values=str(alien.pk))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_two_values_of_one_attribute_are_rejected(
    client: Client, shop: SimpleNamespace
) -> None:
    """Какое из двух полотен считать, знает только приславший."""
    response = ask(client, shop, values=f"{shop.silver.pk},{shop.graphite.pk}")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_price_is_in_openapi_schema(client: Client) -> None:
    """Эндпоинт расчёта отражён в OpenAPI-схеме."""
    response = client.get("/api/openapi/schema.json")

    schema = response.json()
    assert "get" in schema["paths"]["/api/price"]
