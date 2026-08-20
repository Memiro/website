"""Плитки витрины — картиночные входы в каталог.

Вход, который стоит показывать на витрине, — посадочная (ADR-0003):
у неё свой ЧПУ, title и h1, и она индексируется. Категория — это тип
товара (CONTEXT.md), а не витринная рубрика: «круглые» и «с подсветкой»
категориями не выражаются. Поэтому главная набирает плитки из
посадочных, а корень каталога остаётся при категориях: это его
собственная структура.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.urls import reverse

from .landings import landing_products
from .models import Category, Landing, Product

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.db.models.fields.files import ImageFieldFile


@dataclass(frozen=True)
class Tile:
    """Плитка витрины: куда ведёт, что подписано, чем проиллюстрирована."""

    url: str
    label: str
    cover: ImageFieldFile | None


def landing_tiles() -> list[Tile]:
    """Плитки главной — опубликованные посадочные.

    Посадочная без товаров пропускается: такая страница отдаёт 404,
    и вести на неё плиткой нельзя. Товары каждой посадочной выбираются
    один раз — и на проверку, и на обложку.
    """
    tiles = []
    for landing in Landing.objects.published().select_related("category"):
        products = landing_products(landing)
        if not products.exists():
            continue
        tiles.append(
            Tile(
                url=landing.get_absolute_url(),
                label=landing.heading,
                # Кадр из админки точнее — макет ставит в плитку
                # конкретный, — но до него плитка показывает то же,
                # что стоит первым на самой посадочной
                cover=landing.cover or _first_cover(products),
            )
        )
    return tiles


def catalog_tiles() -> list[Tile]:
    """Плитки корня каталога — видимые категории.

    Вызывается, только когда `catalog_root_target()` пуст: с одной
    категорией корень до плиток не доходит.
    """
    categories: list[Category] = list(Category.objects.visible())
    covers = _category_covers(categories)
    return [
        Tile(
            url=reverse("category", kwargs={"slug": category.slug}),
            label=category.name,
            cover=covers.get(category.pk),
        )
        for category in categories
    ]


def catalog_root_target() -> Category | None:
    """Категория, в которую корень каталога уводит редиректом.

    С единственной видимой категорией своего содержания у корня нет:
    плитки посадочных уже стоят на главной, а товары и фильтры живут
    в самой категории — показывать её дубль незачем. Ответ делят вьюха
    и sitemap, иначе карта сайта позовёт на редирект.
    """
    categories: list[Category] = list(Category.objects.visible())
    if len(categories) != 1:
        return None
    return categories[0]


def _first_cover(products: QuerySet[Product]) -> ImageFieldFile | None:
    """Кадр первого по витринному порядку товара с фото."""
    product = products.exclude(photo_large="", photo_small="").first()
    return product.main_photo if product else None


def _category_covers(
    categories: list[Category],
) -> dict[int, ImageFieldFile]:
    """Обложки категорий: по одному фото на категорию, одним запросом."""
    covers: dict[int, ImageFieldFile] = {}
    products = (
        Product.objects.published()
        .filter(category__in=categories)
        .exclude(photo_large="", photo_small="")
        .by_popularity()
    )
    for product in products:
        photo = product.main_photo
        if photo is not None:
            covers.setdefault(product.category_id, photo)
    return covers
