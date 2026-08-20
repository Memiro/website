"""sitemap.xml из базы: статика, категории, товары, посадочные.

Хост берётся из запроса (RequestSite) — отдельного справочника доменов
проект не держит, переезд домена не требует правки данных.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from memiro.catalog.landings import landing_products
from memiro.catalog.models import Category, Landing, Product

if TYPE_CHECKING:
    from datetime import datetime

    from django.db.models import QuerySet

# Страницы, у которых нет своей записи в базе
STATIC_ROUTES = ("home", "catalog", "works", "about", "delivery", "contacts")


class StaticSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self) -> list[str]:
        return list(STATIC_ROUTES)

    def location(self, item: str) -> str:
        return reverse(item)


class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self) -> QuerySet[Category]:
        return Category.objects.visible()

    def location(self, item: Category) -> str:
        return reverse("category", kwargs={"slug": item.slug})


class LandingSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self) -> list[Landing]:
        """Только те посадочные, которые действительно открываются:
        без подходящих товаров страница отдаёт 404."""
        return [
            landing
            for landing in Landing.objects.published().select_related(
                "category"
            )
            if landing_products(landing).exists()
        ]

    def location(self, item: Landing) -> str:
        return item.get_absolute_url()


class ProductSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self) -> QuerySet[Product]:
        return Product.objects.published().select_related("category")

    def lastmod(self, item: Product) -> datetime:
        return item.created_at

    def location(self, item: Product) -> str:
        return reverse(
            "product",
            kwargs={
                "category_slug": item.category.slug,
                "slug": item.slug,
            },
        )


SITEMAPS = {
    "static": StaticSitemap,
    "categories": CategorySitemap,
    "landings": LandingSitemap,
    "products": ProductSitemap,
}
