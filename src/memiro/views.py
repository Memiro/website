"""Главная витрины: акция, категории, популярное, отзывы и FAQ из БД."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import render

from memiro.catalog.models import Category, Product
from memiro.catalog.views import category_tiles
from memiro.content.models import FaqEntry, Promo, Review

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

# Ленты «акция» и «популярное» на главной — не длиннее одной прокрутки
TRACK_SIZE = 8


def home(request: HttpRequest) -> HttpResponse:
    published = Product.objects.published().select_related("category")
    # Блок акции целиком управляется из админки (тикет 08): без
    # опубликованной акции шаблон не рисует и её ленту товаров
    promo = Promo.objects.published().first()
    return render(
        request,
        "home.html",
        {
            "categories": category_tiles(list(Category.objects.visible())),
            "popular": published.filter(is_popular=True).order_by(
                "order", "name"
            )[:TRACK_SIZE],
            "promo": promo,
            "sale": published.filter(is_promo=True).order_by("order", "name")[
                :TRACK_SIZE
            ],
            # Опубликованный отзыв обязан быть виден: потолка на главной нет
            "reviews": Review.objects.published(),
            "faq": FaqEntry.objects.published(),
        },
    )
