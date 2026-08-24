"""Контекст, доступный каждому шаблону витрины."""

from typing import TYPE_CHECKING

from memiro.content.models import SiteContacts
from memiro.inquiries import limits

if TYPE_CHECKING:
    from django.http import HttpRequest


# Строка контактов, уже прочитанная в этом запросе
_CONTACTS_ATTR = "memiro_contacts"


def site_contacts(request: HttpRequest) -> SiteContacts:
    """Контакты студии — один запрос в базу на весь HTTP-запрос.

    Страница спрашивает их дважды: шаблоном и разметкой
    (`seo/structured.py`), а строка в базе одна и та же.
    """
    cached = getattr(request, _CONTACTS_ATTR, None)
    if cached is None:
        cached = SiteContacts.load()
        setattr(request, _CONTACTS_ATTR, cached)
    return cached


def contacts(request: HttpRequest) -> dict[str, SiteContacts]:
    """Контакты студии из админки (`content.SiteContacts`).

    В шаблон уходит сама строка: имена полей у неё те же, что были
    ключами словаря в коде, — шаблоны о переезде не знают.
    """
    return {"contacts": site_contacts(request)}


def inquiry_limits(request: HttpRequest) -> dict[str, dict[str, int]]:  # noqa: ARG001
    """Границы заявки — в шаблон и оттуда в `shop.js` (см. limits.py)."""
    return {
        "inquiry_limits": {
            "max_items": limits.MAX_ITEMS,
            "min_phone_digits": limits.MIN_PHONE_DIGITS,
        },
    }
