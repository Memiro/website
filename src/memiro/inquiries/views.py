"""Подборка: страница-оболочка, наполняет её клиент.

Подборка живёт в localStorage браузера (тикет 07), поэтому сервер
отдаёт только каркас; названия и цены страница забирает у
`/api/products` — цена остаётся серверной правдой.

Адрес `/cart/` остался прежним намеренно (тикет 13): переименование
ради красоты — лишний редирект, а покупатель адрес не читает. Витрина
при этом слова «корзина» не произносит.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import render

from memiro.seo import structured
from memiro.seo.meta import NOINDEX, PageMeta, title

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


def cart(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "inquiries/cart.html",
        {
            # Личная подборка посетителя: в индексе ей делать нечего
            "meta": PageMeta(
                title=title("Заявка"),
                description="Ваша подборка зеркал memiro для заявки.",
                robots=NOINDEX,
            ),
            "breadcrumbs": structured.home_crumbs(structured.Crumb("Заявка")),
        },
    )
