"""Отправка заявки: тарифы фикстуры, состав подборки и POST на эндпоинт.

Нужны всем, кто проверяет заявку, — и приёму, и журналу, и письму
менеджеру, — чтобы третий такой тест не переписывал их в третий раз
(тот же приём, что в `sources.py`). Само зеркало живёт фикстурой
`calculable` в `conftest.py`: фикстуру pytest должен найти сам, без
импорта в каждом модуле.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.test import Client

if TYPE_CHECKING:
    from types import SimpleNamespace

    # Тип ответа тестового клиента живёт только в стабах django-stubs
    from django.test.client import (
        _MonkeyPatchedWSGIResponse as TestResponse,
    )

    from memiro.catalog.models import Product

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
