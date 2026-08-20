"""Корзина и избранное: страницы-оболочки, наполняет их клиент.

Подборка живёт в localStorage браузера (тикет 07), поэтому сервер
отдаёт только каркас; названия и цены страница забирает у
`/api/products` — цена остаётся серверной правдой.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import render

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


def cart(request: HttpRequest) -> HttpResponse:
    return render(request, "leads/cart.html")


def favorites(request: HttpRequest) -> HttpResponse:
    return render(request, "leads/favorites.html")
