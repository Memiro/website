"""Главная витрины и статические страницы студии."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.shortcuts import render

from memiro.catalog.models import Product
from memiro.catalog.tiles import landing_tiles
from memiro.content.models import FaqEntry
from memiro.seo import structured
from memiro.seo.context_processors import FALLBACK_META
from memiro.seo.meta import PageMeta, clamp
from memiro.seo.meta import title as meta_title

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponse

# Лента «популярное» на главной — не длиннее одной прокрутки
TRACK_SIZE = 8


def home(request: HttpRequest) -> HttpResponse:
    published = Product.objects.published().select_related("category")
    # Акции с витрины сняты (тикет 05 набора `owner-revision`): модель
    # и флаг товара живут в админке, но на главную ни заголовок акции,
    # ни её лента не идут. Отзывы сняты следом (тикет 06) — вместе
    # с разметкой рейтинга, порознь они не ездят (ADR-0004)
    return render(
        request,
        "home.html",
        {
            "tiles": landing_tiles(),
            "popular": published.filter(is_popular=True).order_by(
                "order", "name"
            )[:TRACK_SIZE],
            "faq": FaqEntry.objects.published(),
            "meta": FALLBACK_META,
            "business_jsonld": structured.local_business(request),
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
            # Разметка шоурума нужна и здесь: адрес с часами живут
            # на «Контактах», а не только на главной
            context["business_jsonld"] = structured.local_business(request)
        return render(request, page.template, context)

    return view
