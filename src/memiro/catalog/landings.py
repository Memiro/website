"""Товары посадочной — одно правило для страницы, ссылок и sitemap.

Посадочная сужает категорию условиями из админки; выборка строится тем
же аппаратом, что и пользовательские фильтры (ADR-0003), поэтому
второго способа сузить каталог в проекте нет.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .filters import FILTERABLE_KINDS, CatalogFilters
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

    None — условие ссылается на атрибут, который сменил категорию или
    тип: сузить им категорию нечем, товаров у такой посадочной нет.
    """
    attributes = list(
        landing.category.attributes.filter(
            kind__in=FILTERABLE_KINDS
        ).prefetch_related("values")
    )
    by_id = {attribute.pk: attribute for attribute in attributes}
    choice: dict[Attribute, tuple[AttributeValue, ...]] = {}
    flags: dict[Attribute, tuple[bool, ...]] = {}
    conditions = landing.conditions.select_related("attribute", "value_option")
    for condition in conditions:
        attribute = by_id.get(condition.attribute_id)
        if attribute is None:
            return None
        if attribute.kind == Attribute.Kind.CHOICE:
            if condition.value_option is None:
                return None
            choice[attribute] = (condition.value_option,)
        else:
            flags[attribute] = (bool(condition.value_bool),)
    return CatalogFilters(attributes, choice, flags)
