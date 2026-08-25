"""Дефолты SEO для каждого шаблона: мета, canonical, крошки.

Представление кладёт свои `meta`/`canonical`/`breadcrumbs` в контекст и
перекрывает дефолт — страница без своей меты остаётся с осмысленной.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .absolute import absolute_uri
from .meta import SITE_NAME, PageMeta

if TYPE_CHECKING:
    from django.http import HttpRequest

FALLBACK_META = PageMeta(
    title="memiro — интерьерные зеркала на заказ в Санкт-Петербурге",
    description=(
        "Производство интерьерных зеркал на заказ в Санкт-Петербурге: "
        "изготовление по вашим размерам, доставка и установка."
    ),
)


def defaults(request: HttpRequest) -> dict[str, Any]:
    return {
        "meta": FALLBACK_META,
        "site_name": SITE_NAME,
        # Canonical по умолчанию — сама страница; каталог и карточка
        # перекрывают его по ADR-0003
        "canonical": absolute_uri(request, request.path),
        "breadcrumbs": [],
    }
