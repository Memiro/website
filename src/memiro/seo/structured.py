"""JSON-LD страниц: BreadcrumbList, LocalBusiness, Product.

Разметка собирается словарями на Python и печатается тегом `{% jsonld %}`
— шаблоны не собирают JSON руками.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.templatetags.static import static
from django.urls import reverse

from memiro.context_processors import site_contacts
from .meta import DEFAULT_OG_IMAGE, SITE_NAME

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from datetime import time

    from django.http import HttpRequest

    from memiro.catalog.models import Category, Product
    from memiro.content.models import Review, SiteContacts


# Шоурум работает ежедневно (часы студии) — расписание разметки
# перечисляет все семь дней
EVERY_DAY = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


@dataclass(frozen=True)
class Crumb:
    """Ступень хлебных крошек; у текущей страницы ссылки нет."""

    name: str
    url: str = ""


def home_crumbs(*rest: Crumb) -> list[Crumb]:
    """Крошки от «Главной» — она первая ступень на любой странице."""
    return [Crumb("Главная", reverse("home")), *rest]


def category_crumbs(category: Category, *rest: Crumb) -> list[Crumb]:
    """Крошки «Главная → Каталог → категория» и что идёт после.

    Ими живут и сама категория, и карточка товара, и посадочная.
    """
    url = reverse("category", kwargs={"slug": category.slug}) if rest else ""
    crumb = Crumb(category.name, url)
    return home_crumbs(Crumb("Каталог", reverse("catalog")), crumb, *rest)


def breadcrumb_list(
    request: HttpRequest, crumbs: Sequence[Crumb]
) -> dict[str, Any] | None:
    """BreadcrumbList: на главной крошек нет — и разметки тоже."""
    if len(crumbs) < 2:  # noqa: PLR2004 — одна ступень цепочкой не является
        return None
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            _crumb_item(request, position, crumb)
            for position, crumb in enumerate(crumbs, start=1)
        ],
    }


def _crumb_item(
    request: HttpRequest, position: int, crumb: Crumb
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "@type": "ListItem",
        "position": position,
        "name": str(crumb.name),
    }
    if crumb.url:
        item["item"] = request.build_absolute_uri(str(crumb.url))
    return item


def local_business(
    request: HttpRequest, reviews: Iterable[Review] = ()
) -> dict[str, Any]:
    """Шоурум в Санкт-Петербурге: адрес, часы, связь.

    Рейтинг добавляется только из настоящих отзывов, занесённых в
    админку (CONTEXT.md): выдуманных оценок в разметке не бывает.
    """
    contacts = site_contacts(request)
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "@id": request.build_absolute_uri(reverse("home")) + "#business",
        "name": SITE_NAME,
        "description": (
            "Производство интерьерных зеркал на заказ в Санкт-Петербурге: "
            "изготовление, доставка и установка."
        ),
        "url": request.build_absolute_uri(reverse("home")),
        # Кадр для локального сниппета — тот же, что уходит в OG
        "image": request.build_absolute_uri(static(DEFAULT_OG_IMAGE)),
    }
    # Незаполненного контакта разметка не называет — пустой телефон
    # и профиль пустой строкой такое же враньё поисковику, как
    # выдуманное расписание ниже
    if contacts.phone:
        data["telephone"] = contacts.phone
    if contacts.email:
        data["email"] = contacts.email
    if contacts.city or contacts.street:
        data["address"] = {
            "@type": "PostalAddress",
            "addressCountry": "RU",
            "addressLocality": contacts.city,
            "streetAddress": contacts.street,
        }
    profiles = [
        link
        for link in (contacts.telegram, contacts.vk, contacts.avito)
        if link
    ]
    if profiles:
        data["sameAs"] = profiles
    hours = _opening_hours(contacts)
    if hours:
        data["openingHoursSpecification"] = hours
    rating = _aggregate_rating(reviews)
    if rating:
        data["aggregateRating"] = rating
    return data


def _opening_hours(contacts: SiteContacts) -> list[dict[str, Any]]:
    """Расписание шоурума — только если часы заданы.

    Незаданные часы разметка пропускает: выдуманное расписание — такое
    же враньё поисковику, как выдуманный рейтинг.
    """
    if not contacts.has_schedule:
        return []
    return [
        {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": list(EVERY_DAY),
            "opens": _hhmm(contacts.opens),
            "closes": _hhmm(contacts.closes),
        }
    ]


def _hhmm(moment: time | None) -> str:
    """Время так, как его читает schema.org: ЧЧ:ММ."""
    return moment.strftime("%H:%M") if moment else ""


def _aggregate_rating(reviews: Iterable[Review]) -> dict[str, Any] | None:
    ratings = [review.rating for review in reviews]
    if not ratings:
        return None
    return {
        "@type": "AggregateRating",
        "ratingValue": round(sum(ratings) / len(ratings), 1),
        "reviewCount": len(ratings),
    }


def product_markup(request: HttpRequest, product: Product) -> dict[str, Any]:
    """Product карточки с AggregateOffer: цена «от» в рублях."""
    url = request.build_absolute_uri(
        reverse(
            "product",
            kwargs={
                "category_slug": product.category.slug,
                "slug": product.slug,
            },
        )
    )
    photo = product.main_photo
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "url": url,
        "category": product.category.name,
        "brand": {"@type": "Brand", "name": SITE_NAME},
    }
    # AggregateOffer, а не Offer: цена товара — стоимость минимальной
    # конфигурации, витрина показывает её как «от X ₽» (CONTEXT.md),
    # и точной ценой объявлять её нельзя. У товара без вариантов цены
    # нет вовсе — предложения тогда нет тоже: AggregateOffer без
    # lowPrice разметкой не является
    if product.has_price:
        data["offers"] = {
            "@type": "AggregateOffer",
            "url": url,
            "priceCurrency": "RUB",
            "lowPrice": product.price,
            "itemCondition": "https://schema.org/NewCondition",
            # Понятия «в наличии» в модели нет: всё производится
            # под клиента (CONTEXT.md)
            "availability": "https://schema.org/MadeToOrder",
            "seller": {"@type": "Organization", "name": SITE_NAME},
        }
    if product.description:
        data["description"] = product.description
    if product.article:
        data["sku"] = product.article
    if photo:
        data["image"] = request.build_absolute_uri(photo.url)
    return data
