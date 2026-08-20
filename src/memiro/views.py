"""Главная витрины и статические страницы студии."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import render

from memiro.catalog.models import Category, Product
from memiro.catalog.views import category_tiles
from memiro.content.models import FaqEntry, Promo, Review
from memiro.seo import structured
from memiro.seo.context_processors import FALLBACK_META
from memiro.seo.meta import PageMeta, clamp, title

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

# Ленты «акция» и «популярное» на главной — не длиннее одной прокрутки
TRACK_SIZE = 8


def home(request: HttpRequest) -> HttpResponse:
    published = Product.objects.published().select_related("category")
    # Блок акции целиком управляется из админки (тикет 08): без
    # опубликованной акции шаблон не рисует и её ленту товаров
    promo = Promo.objects.published().first()
    # Опубликованный отзыв обязан быть виден: потолка на главной нет
    reviews = Review.objects.published()
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
            "reviews": reviews,
            "faq": FaqEntry.objects.published(),
            "meta": FALLBACK_META,
            "business_jsonld": structured.local_business(request, reviews),
        },
    )


def about(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "pages/about.html",
        {
            "meta": PageMeta(
                title=title("О студии"),
                description=clamp(
                    "Студия memiro: собственное производство интерьерных "
                    "зеркал в Санкт-Петербурге — от резки стекла "
                    "до установки у клиента."
                ),
            ),
            "breadcrumbs": structured.home_crumbs(structured.Crumb("О нас")),
        },
    )


def delivery(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "pages/delivery.html",
        {
            "meta": PageMeta(
                title=title("Доставка и возврат"),
                description=clamp(
                    "Доставка и установка зеркал memiro по Санкт-Петербургу "
                    "и области, сроки изготовления и условия возврата "
                    "изделий по индивидуальным размерам."
                ),
            ),
            "breadcrumbs": structured.home_crumbs(
                structured.Crumb("Доставка и возврат")
            ),
        },
    )


def contacts(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "pages/contacts.html",
        {
            "meta": PageMeta(
                title=title("Контакты и шоурум"),
                description=clamp(
                    "Шоурум memiro в Санкт-Петербурге: адрес, часы работы, "
                    "телефон и мессенджеры для связи со студией."
                ),
            ),
            "breadcrumbs": structured.home_crumbs(
                structured.Crumb("Контакты")
            ),
            # Рейтинг из отзывов живёт на главной, где сами отзывы
            # и показываются; «Контакты» остаются страницей без базы
            "business_jsonld": structured.local_business(request),
        },
    )
