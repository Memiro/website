"""Общая обстановка тестов о заявке: считаемое зеркало и отправка формы.

Зеркало с тарифами и POST на эндпоинт нужны всем, кто проверяет заявку, —
и приёму, и журналу, и письму менеджеру. Собраны здесь, чтобы третий такой
тест не переписывал их в третий раз (тот же приём, что в `sources.py`).
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from django.test import Client

if TYPE_CHECKING:
    # Тип ответа тестового клиента живёт только в стабах django-stubs
    from django.test.client import (
        _MonkeyPatchedWSGIResponse as TestResponse,
    )

from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    PricingSettings,
    Product,
    ProductAttribute,
)

# Условные тарифы: полотно 4 000 ₽/м², подогрев 3 500 ₽/шт
GLASS_RATE = Decimal(4000)
HEATING_RATE = Decimal(3500)
# Зеркало 800 × 600 — 0,48 м²: 1 920 ₽ полотна, с подогревом 5 420 ₽,
# итог округляется вверх до сотни. Имена намеренно свои: у фикстуры
# `shop` в test_price_endpoint.py другие тарифы и другие числа
SILVER_TOTAL = 2000
SILVER_WITH_HEATING = 5500
# Предел производства: длинная сторона до 2 500 мм, короткая до 1 500
MAX_LONG_SIDE_MM = 2500
MAX_SHORT_SIDE_MM = 1500


def item(
    product: Product, wish: str = "", **configuration: object
) -> dict[str, object]:
    """Позиция подборки: товар, его настройки и его пожелание.

    Настройки — конфигурация расчёта (ADR-0009); пожелание — свободный
    текст покупателя об этом зеркале, в расчёт он не идёт (тикет 15).
    """
    return {
        "product": product.pk,
        "configuration": configuration or None,
        "wish": wish,
    }


def payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "Анна",
        "phone": "+7 981 000-00-00",
        "email": "anna@example.com",
        "comment": "Нужен замер",
        "consent": True,
        "source": "cart",
        "items": [],
    }
    return body | overrides


def post_inquiry(client: Client, **overrides: object) -> TestResponse:
    return client.post(
        "/api/inquiries",
        data=payload(**overrides),
        content_type="application/json",
    )


@pytest.fixture
def calculable(db: None) -> SimpleNamespace:
    """Зеркало в считаемом наборе: полотно и подогрев меняет покупатель."""
    PricingSettings.objects.create(
        max_long_side_mm=MAX_LONG_SIDE_MM,
        max_short_side_mm=MAX_SHORT_SIDE_MM,
    )
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
    # Умолчание товара: бесплатное «нет» — покупатель его и заменяет
    no_heating = AttributeValue.objects.create(
        attribute=heating_attribute, value="Нет", order=1
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
    return SimpleNamespace(
        product=product,
        silver=silver,
        heating=heating,
        no_heating=no_heating,
    )


def post_calculated(
    client: Client,
    calculable: SimpleNamespace,
    *,
    width_mm: int = 800,
    height_mm: int = 600,
    values: list[int] | None = None,
    **overrides: object,
) -> TestResponse:
    return post_inquiry(
        client,
        items=[
            item(
                calculable.product,
                width_mm=width_mm,
                height_mm=height_mm,
                values=[calculable.silver.pk] if values is None else values,
            )
        ],
        **overrides,
    )
