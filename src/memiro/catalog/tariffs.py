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

from decimal import Decimal
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
            "attribute", "value_option__attribute"
        ).prefetch_related("attribute__values"),
    )


def declared_values(product: Product) -> dict[int, AttributeValue]:
    """Значения справочника, названные товаром, — по атрибуту.

    Атрибуты «да/нет» и числовые сюда не попадают: у товара они стоят
    не строкой справочника. Числовые приходят в расчёт своим путём —
    `counted_values()`. Берётся `all()`, чтобы попадать в кэш
    `product_values()`.
    """
    return {
        row.value_option.attribute_id: row.value_option
        for row in product.attribute_values.all()
        if row.value_option is not None
    }


def counted_values(
    product: Product,
) -> list[tuple[AttributeValue, Decimal]]:
    """Числовые значения товара со ставкой, которую они умножают.

    Число у товара говорит не «что выбрано», а «сколько раз»: два
    выреза стоят вдвое (тикет 22). Ставка при этом остаётся там же,
    где у всех остальных, — в справочнике; у числового атрибута его
    единственная строка и есть тариф за единицу.

    Ноль и пустое — не признак: вырезов нет, статьи тоже.
    """
    counted: list[tuple[AttributeValue, Decimal]] = []
    for row in product.attribute_values.all():
        if row.value_number is None or row.value_number <= 0:
            continue
        tariff = next(iter(row.attribute.values.all()), None)
        if tariff is not None:
            counted.append((tariff, row.value_number))
    return counted


def limits_from_settings() -> pricing.PricingLimits:
    """Границы расчёта из админки; без строки параметров их нет."""
    settings = PricingSettings.objects.first()
    if settings is None:
        return pricing.NO_LIMITS
    return pricing.PricingLimits(
        min_area_m2=settings.min_area_m2,
        min_order_total=settings.min_order_total,
        max_long_side_mm=settings.max_long_side_mm,
        max_short_side_mm=settings.max_short_side_mm,
    )


def configuration(
    product: Product,
    *,
    width_mm: int,
    height_mm: int,
    chosen: Iterable[AttributeValue] = (),
) -> pricing.Configuration:
    """Что считать: габариты и значения атрибутов изделия.

    Умолчания товара берутся `declared_values()`; в одиночном вызове
    префетч под них ставит вызывающий.
    """
    values = declared_values(product)
    values.update({value.attribute_id: value for value in chosen})
    return pricing.Configuration(
        width_mm=width_mm,
        height_mm=height_mm,
        values=tuple(_selected(value) for value in values.values())
        + tuple(
            _selected(tariff, quantity=quantity)
            for tariff, quantity in counted_values(product)
        ),
    )


def _selected(
    value: AttributeValue, *, quantity: Decimal = Decimal(1)
) -> pricing.SelectedValue:
    """Строка справочника глазами движка."""
    return pricing.SelectedValue(
        label=value.full_label,
        unit=pricing.Unit(value.unit) if value.unit else None,
        rate=value.rate,
        quantity=quantity,
        scaled_by_shape=value.scaled_by_shape,
    )


def price_of(
    product: Product,
    *,
    width_mm: int,
    height_mm: int,
    chosen: Iterable[AttributeValue],
    limits: pricing.PricingLimits | None = None,
) -> int:
    """Цена изделия товара — сборка и движок одним вызовом.

    Спрашивают её двое, и им важно получить одно и то же число:
    пересчёт, который записывает цену предпосчитанному варианту
    (`catalog.repricing`), и конструктор в карточке товара, который
    показывает её владельцу до сохранения (`catalog.variants`).
    Считай они порознь, владелец добавлял бы вариант, увидев одно
    число, а в списке находил другое (тикет 18).

    Предел производства сюда не входит и не должен: варианты заводит
    тот, кто знает, что производство возьмёт, — движок цены о верхних
    границах не спрашивает вовсе (CONTEXT.md, «Предпосчитанный
    вариант»).

    Границы принимаются готовыми ради пересчёта пачки: они одни на
    сайт, и читать их на каждый вариант незачем.
    """
    return price(
        configuration(
            product,
            width_mm=width_mm,
            height_mm=height_mm,
            chosen=chosen,
        ),
        limits=limits,
    ).total


def price(
    configuration: pricing.Configuration,
    *,
    limits: pricing.PricingLimits | None = None,
) -> pricing.Price:
    """Цена конфигурации — итог и статьи, из которых он сложился.

    Границы готовыми принимаются ради пересчёта пачки вариантов: они
    одни на сайт, и читать их на каждый вариант незачем.
    """
    return pricing.calculate_price(
        configuration,
        limits=limits_from_settings() if limits is None else limits,
    )
