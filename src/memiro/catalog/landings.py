"""Товары посадочной — одно правило для страницы и для sitemap.

Посадочная сужает категорию условиями из админки; выборка строится тем
же разбором, что и пользовательские фильтры (ADR-0003), поэтому второго
способа сузить каталог в проекте нет.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .filters import CatalogFilters, FilterError
from .models import POPULAR_ORDERING, Product

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from .models import Landing


def landing_products(landing: Landing) -> QuerySet[Product]:
    """Опубликованные товары посадочной в витринном порядке.

    Условие, указывающее на удалённое значение атрибута, делает
    посадочную пустой: страницы у такой всё равно нет.
    """
    base = landing.category.products.published().select_related("category")
    try:
        filters = CatalogFilters.parse(landing.category, landing.query())
    except FilterError:
        return Product.objects.none()
    return filters.apply(base).order_by(*POPULAR_ORDERING)
