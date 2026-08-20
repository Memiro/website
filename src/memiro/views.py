"""Главная витрины: блоки «акция», «категории», «популярное» из БД."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import render

from memiro.catalog.models import Category, Product
from memiro.catalog.views import category_tiles

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

# Ленты «акция» и «популярное» на главной — не длиннее одной прокрутки
TRACK_SIZE = 8


def home(request: HttpRequest) -> HttpResponse:
    published = Product.objects.published().select_related("category")
    return render(
        request,
        "home.html",
        {
            "categories": category_tiles(list(Category.objects.visible())),
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
