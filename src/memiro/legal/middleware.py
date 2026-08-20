"""Ответ витрины зависит от cookie-согласия — говорим это кешам явно."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.cache import patch_vary_headers

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponse


def consent_vary(
    get_response: Callable[[HttpRequest], HttpResponse],
) -> Callable[[HttpRequest], HttpResponse]:
    """`Vary: Cookie` на каждый ответ витрины.

    Cookie-баннер и счётчик Метрики решаются по cookie на ЛЮБОЙ
    странице, а Django ставит заголовок сам только там, где потрогали
    сессию или CSRF-токен: `/contacts/`, `/privacy/` и страницы
    каталога его не трогают и уходят без Vary.

    Без заголовка первый же кеширующий слой — прокси, CDN или
    `cache_page` — раздал бы ответ с чужим согласием всем подряд,
    и гарантия ADR-0006 сломалась бы молча. Заголовок дешевле разбора
    такого инцидента.
    """

    def middleware(request: HttpRequest) -> HttpResponse:
        response = get_response(request)
        patch_vary_headers(response, ("Cookie",))
        return response

    return middleware
