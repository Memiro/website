"""Единственное место, где справочник превращается в тарифы движка.

Движок цены (`memiro.pricing`) моделей Django не знает: конфигурация
и пороги приходят в него готовой структурой. Собирается она здесь —
и только здесь. Ни вьюха, ни эндпоинт, ни пересчёт вариантов в
справочник сами не ходят (спека расчёта, «одна точка сборки тарифов»).

Конфигурация товара — его собственные значения атрибутов; выбранное
покупателем или заведённое у варианта перекрывает умолчание товара по
атрибуту, а не добавляется к нему второй строкой.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Prefetch

from memiro import pricing
from .models import AttributeValue, PricingSettings, ProductAttribute

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .models import Product


def product_values(prefix: str = "") -> Prefetch:
    """Что расчёту нужно загрузить у товара — одним `prefetch_related`.

    Знание «цене нужны значения атрибутов вместе со справочником»
    живёт здесь же, где сборка: вызывающему остаётся подставить
    префикс своего пути до товара.
    """
    return Prefetch(
        f"{prefix}attribute_values",
        queryset=ProductAttribute.objects.select_related(
            "value_option__attribute"
        ),
    )


def thresholds() -> pricing.PricingThresholds:
    """Пороги расчёта из админки; без строки порогов их нет."""
    settings = PricingSettings.objects.first()
    if settings is None:
        return pricing.NO_THRESHOLDS
    return pricing.PricingThresholds(
        min_area_m2=settings.min_area_m2,
        min_order_total=settings.min_order_total,
    )


def configuration(
    product: Product,
    *,
    width_mm: int,
    height_mm: int,
    chosen: Iterable[AttributeValue] = (),
) -> pricing.Configuration:
    """Что считать: габариты и значения атрибутов изделия.

    Значения товара берутся `all()`, чтобы пачечный пересчёт попадал
    в кэш `product_values()`; в одиночном вызове тот же префетч ставит
    вызывающий. Атрибуты «да/нет» и числовые в расчёт не входят: тариф
    живёт у значения справочника, а у них значения справочника нет.
    """
    values = {
        row.value_option.attribute_id: row.value_option
        for row in product.attribute_values.all()
        if row.value_option is not None
    }
    values.update({value.attribute_id: value for value in chosen})
    return pricing.Configuration(
        width_mm=width_mm,
        height_mm=height_mm,
        values=tuple(_selected(value) for value in values.values()),
    )


def _selected(value: AttributeValue) -> pricing.SelectedValue:
    """Строка справочника глазами движка."""
    return pricing.SelectedValue(
        label=value.full_label,
        unit=pricing.Unit(value.unit) if value.unit else None,
        rate=value.rate,
        scaled_by_shape=value.scaled_by_shape,
    )


def price(
    configuration: pricing.Configuration,
    *,
    limits: pricing.PricingThresholds | None = None,
) -> pricing.Price:
    """Цена конфигурации — итог и статьи, из которых он сложился.

    Пороги готовыми принимаются ради пересчёта пачки вариантов: они
    одни на сайт, и читать их на каждый вариант незачем.
    """
    return pricing.calculate_price(
        configuration,
        thresholds=thresholds() if limits is None else limits,
    )
