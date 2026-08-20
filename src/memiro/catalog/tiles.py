"""Плитки витрины — картиночные входы в каталог.

Вход, который стоит показывать на витрине, — посадочная (ADR-0003):
у неё свой ЧПУ, title и h1, и она индексируется. Категория — это тип
товара (CONTEXT.md), а не витринная рубрика: «круглые» и «с подсветкой»
категориями не выражаются. Поэтому главная набирает плитки из
посадочных, а корень каталога остаётся при категориях, пока их больше
одной: без него во второй тип товара не попасть.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.urls import reverse

from .landings import landing_products, visible_landings
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

    Пустые пропускаются: такая страница отдаёт 404, и вести на неё
    плиткой нельзя.
    """
    return [
        Tile(
            url=landing.get_absolute_url(),
            label=landing.heading,
            cover=landing.cover or _landing_cover(landing),
        )
        for landing in visible_landings(_published_landings())
    ]


def catalog_tiles() -> list[Tile]:
    """Плитки корня каталога.

    Категорий несколько — корень даёт вход в каждую: это его
    собственная структура, и без плитки во второй тип товара не
    попасть. Категория одна — показывать одну плитку незачем, и корень
    отдаёт витринные плитки посадочных.
    """
    categories = list(Category.objects.visible())
    if len(categories) > 1:
        return _category_tiles(categories)
    return landing_tiles()


def catalog_root_target() -> Category | None:
    """Категория, в которую корень каталога уводит редиректом.

    Единственная категория без посадочных оставила бы корень со списком
    из одной плитки — вместо этого он ведёт прямо в неё. Ответ делят
    вьюха и sitemap: иначе карта сайта позовёт на редирект.
    """
    categories: list[Category] = list(Category.objects.visible())
    if len(categories) != 1 or visible_landings(_published_landings()):
        return None
    return categories[0]


def _published_landings() -> QuerySet[Landing]:
    return Landing.objects.published().select_related("category")


def _category_tiles(categories: list[Category]) -> list[Tile]:
    """Плитки категорий — структура каталога, а не витрины."""
    covers = _category_covers(categories)
    return [
        Tile(
            url=reverse("category", kwargs={"slug": category.slug}),
            label=category.name,
            cover=covers.get(category.pk),
        )
        for category in categories
    ]


def _landing_cover(landing: Landing) -> ImageFieldFile | None:
    """Запасная обложка: первый товар посадочной с фото.

    Кадр из админки точнее — макет ставит в плитку конкретный, — но до
    него плитка показывает то же, что стоит первым на самой посадочной.
    """
    product = (
        landing_products(landing)
        .exclude(photo_large="", photo_small="")
        .first()
    )
    return product.main_photo if product else None


def _category_covers(
    categories: list[Category],
) -> dict[int, ImageFieldFile]:
    """Обложки категорий: по одному фото на категорию, одним запросом.

    Побеждает первый по витринному порядку товар с фото.
    """
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
