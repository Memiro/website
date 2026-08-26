"""Фикстуры, общие для всех тестов.

Считаемое зеркало спрашивают трое — приём заявки, журнал и письмо
менеджеру. Место фикстуры — здесь: pytest находит её сам, и ни один
модуль не тащит её импортом.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    PricingSettings,
    Product,
    ProductAttribute,
)
from tests.inquiries import (
    GLASS_RATE,
    HEATING_RATE,
    MAX_LONG_SIDE_MM,
    MAX_SHORT_SIDE_MM,
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
