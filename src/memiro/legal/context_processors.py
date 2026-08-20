"""Юридический контекст витрины: реквизиты, cookie-баннер, аналитика."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings

from . import consent, seller
from .privacy import PRIVACY_VERSION

if TYPE_CHECKING:
    from django.http import HttpRequest


def _metrika_id() -> str:
    """Номер счётчика Метрики — только если это действительно номер.

    Значение уезжает в тело `<script>`, где экранирование шаблонов
    не спасает. Всё, что не набор цифр, считаем ненастроенным
    счётчиком: сайт остаётся без аналитики, но не без головы.
    """
    value = settings.YANDEX_METRIKA_ID.strip()
    return value if value.isdigit() else ""


def legal(request: HttpRequest) -> dict[str, Any]:
    counter = _metrika_id()
    return {
        "seller": seller.SELLER.requisites(),
        "privacy_version": PRIVACY_VERSION,
        # Разметка Метрики появляется в ответе только после согласия
        "metrika_id": counter if consent.accepted(request) else "",
        "cookie_choice": {
            # Без счётчика спрашивать не о чем: сайт ставит только
            # строго необходимые cookie (CSRF, сессия, сам выбор)
            "needed": bool(counter) and not consent.answered(request),
            "cookie": consent.COOKIE_NAME,
            "accepted": consent.ACCEPTED,
            "declined": consent.DECLINED,
            "max_age": consent.MAX_AGE,
        },
    }
