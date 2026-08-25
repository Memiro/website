"""Переезд домена: 404 разводится по карте старых адресов (тикет 09)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import HttpResponsePermanentRedirect

from memiro import errors
from .models import LegacyUrl, normalize_path

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponse

NOT_FOUND = 404


class LegacyUrlMiddleware:
    """На 404 ищет путь в карте переезда: 301 на новый адрес или 410.

    Запрос в базу делается только на 404 — живые страницы карты не
    касаются.
    """

    def __init__(
        self, get_response: Callable[[HttpRequest], HttpResponse]
    ) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if response.status_code != NOT_FOUND:
            return response
        rule = LegacyUrl.objects.filter(
            old_path=normalize_path(request.path)
        ).first()
        if rule is None:
            return response
        if rule.is_gone:
            # Своя страница, а не пустой `HttpResponseGone`: адрес живой,
            # человек по нему пришёл и должен увидеть, куда идти дальше
            # (тикет 12 набора `owner-revision`)
            return errors.GONE.view(request)
        return HttpResponsePermanentRedirect(rule.new_path)
