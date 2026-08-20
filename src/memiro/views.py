"""Главная витрины и статические страницы студии."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.shortcuts import render

from memiro.catalog.models import Category, Product
from memiro.catalog.views import category_tiles
from memiro.content.models import FaqEntry, Promo, Review
from memiro.seo import structured
from memiro.seo.context_processors import FALLBACK_META
from memiro.seo.meta import PageMeta, clamp
from memiro.seo.meta import title as meta_title

if TYPE_CHECKING:
    from collections.abc import Callable

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


@dataclass(frozen=True)
class StaticPage:
    """Страница с текстом в шаблоне: своя мета, своя крошка, без базы.

    Одна запись описывает страницу целиком — из этой таблицы растут
    и маршруты (`urls.py`), и sitemap, так что новая страница заводится
    в одном месте.
    """

    route: str
    template: str
    crumb: str
    title: str
    description: str

    def context(self) -> dict[str, object]:
        return {
            "meta": PageMeta(
                title=meta_title(self.title),
                description=clamp(self.description),
            ),
            "breadcrumbs": structured.home_crumbs(
                structured.Crumb(self.crumb)
            ),
        }


STATIC_PAGES = (
    StaticPage(
        route="about",
        template="pages/about.html",
        crumb="О нас",
        title="О студии",
        description=(
            "Студия memiro: собственное производство интерьерных зеркал "
            "в Санкт-Петербурге — от резки стекла до установки у клиента."
        ),
    ),
    StaticPage(
        route="delivery",
        template="pages/delivery.html",
        crumb="Доставка и возврат",
        title="Доставка и возврат",
        description=(
            "Доставка и установка зеркал memiro по Санкт-Петербургу "
            "и области, сроки изготовления и условия возврата изделий "
            "по индивидуальным размерам."
        ),
    ),
    StaticPage(
        route="privacy",
        template="pages/privacy.html",
        crumb="Политика обработки персональных данных",
        title="Политика обработки персональных данных",
        description=(
            "Как студия memiro обрабатывает персональные данные "
            "посетителей сайта: состав данных, цели и сроки хранения, "
            "cookie и Яндекс.Метрика, права субъекта и отзыв согласия."
        ),
    ),
    StaticPage(
        route="contacts",
        template="pages/contacts.html",
        crumb="Контакты",
        title="Контакты и шоурум",
        description=(
            "Шоурум memiro в Санкт-Петербурге: адрес, часы работы, "
            "телефон и мессенджеры для связи со студией."
        ),
    ),
)


def static_page(page: StaticPage) -> Callable[[HttpRequest], HttpResponse]:
    """Представление одной статической страницы."""

    def view(request: HttpRequest) -> HttpResponse:
        context = page.context()
        if page.route == "contacts":
            # Разметка шоурума — на «Контактах»; рейтинг из отзывов
            # живёт на главной, где сами отзывы и показываются
            context["business_jsonld"] = structured.local_business(request)
        return render(request, page.template, context)

    return view
