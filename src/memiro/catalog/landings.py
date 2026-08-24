"""Товары посадочной — одно правило для страницы, ссылок и sitemap.

Посадочная сужает категорию условиями из админки; выборка строится тем
же аппаратом, что и пользовательские фильтры (ADR-0003), поэтому
второго способа сузить каталог в проекте нет.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .filters import CatalogFilters, filterable_attributes
from .models import POPULAR_ORDERING, Attribute, Product

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.models import QuerySet

    from .models import AttributeValue, Landing


def landing_products(landing: Landing) -> QuerySet[Product]:
    """Опубликованные товары посадочной в витринном порядке."""
    filters = _filters_of(landing)
    if filters is None:
        return Product.objects.none()
    base = landing.category.products.published().select_related("category")
    return filters.apply(base).order_by(*POPULAR_ORDERING)


def visible_landings(landings: Iterable[Landing]) -> list[Landing]:
    """Посадочные, которые действительно открываются.

    Без подходящих товаров страница отдаёт 404, поэтому такой не место
    ни в ссылках с категории, ни в sitemap.
    """
    return [
        landing for landing in landings if landing_products(landing).exists()
    ]


def _filters_of(landing: Landing) -> CatalogFilters | None:
    """Условия посадочной как готовый набор фильтров категории.

    Тот же аппарат, что и у пользовательских фильтров, и то же
    правило: значения одного атрибута объединяются по ИЛИ, разные
    атрибуты — по И.

    None — сузить категорию нечем: условие ссылается на атрибут,
    который сменил категорию или тип, либо условий не осталось вовсе.
    Товаров у такой посадочной нет.
    """
    attributes = filterable_attributes(landing.category)
    by_id = {attribute.pk: attribute for attribute in attributes}
    choice: dict[Attribute, tuple[AttributeValue, ...]] = {}
    flags: dict[Attribute, tuple[bool, ...]] = {}
    conditions = landing.conditions.select_related("attribute", "value_option")
    # Посадочная без условий — дубль категории, а не страница: без
    # сужения выборка возвращает всю категорию целиком. Форма условий
    # такого не сохранит, но переразметка справочника условие у
    # посадочной снять может (тикет 22), а публикация переключается и
    # прямо в списке, мимо формы
    if not conditions:
        return None
    for condition in conditions:
        attribute = by_id.get(condition.attribute_id)
        if attribute is None:
            return None
        if attribute.kind == Attribute.Kind.CHOICE:
            if condition.value_option is None:
                return None
            # Значения одного атрибута копятся, а не вытесняют друг
            # друга: между собой они по ИЛИ — «в раме» это и алюминий,
            # и багет (CONTEXT.md, «Условие посадочной»)
            choice[attribute] = (
                *choice.get(attribute, ()),
                condition.value_option,
            )
        else:
            flags[attribute] = (
                *flags.get(attribute, ()),
                bool(condition.value_bool),
            )
    return CatalogFilters(attributes, choice, flags)
