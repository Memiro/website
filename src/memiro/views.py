"""Главная витрины: блоки «акция», «категории», «популярное» из БД."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import render

from memiro.catalog.models import Category, Product

if TYPE_CHECKING:
    from django.db.models.fields.files import ImageFieldFile
    from django.http import HttpRequest, HttpResponse

# Ленты «акция» и «популярное» на главной — не длиннее одной прокрутки
TRACK_SIZE = 10


def _covers(categories: list[Category]) -> dict[int, ImageFieldFile]:
    """Обложки плиток: по одному фото на категорию, одним запросом.

    Побеждает первый по витринному порядку товар с фото — так плитка
    показывает то же, что стоит первым в самой категории.
    """
    covers: dict[int, ImageFieldFile] = {}
    products = (
        Product.objects.published()
        .filter(category__in=categories)
        .exclude(photo_small="")
        .by_popularity()
    )
    for product in products:
        covers.setdefault(product.category_id, product.photo_small)
    return covers


def home(request: HttpRequest) -> HttpResponse:
    categories = list(Category.objects.visible())
    covers = _covers(categories)
    published = Product.objects.published().select_related("category")
    return render(
        request,
        "home.html",
        {
            "categories": [
                {"category": category, "cover": covers.get(category.pk)}
                for category in categories
            ],
            "popular": published.filter(is_popular=True).order_by(
                "order", "name"
            )[:TRACK_SIZE],
            # «Акция» как сущность админки приедет тикетом 08; сейчас это
            # ручной флаг товара из тикета 03
            "sale": published.filter(is_promo=True).order_by("order", "name")[
                :TRACK_SIZE
            ],
        },
    )
