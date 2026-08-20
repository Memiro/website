"""Согласие на аналитику: счётчик не грузится, пока его не разрешили.

Это не «Согласие» из формы заявки (то живёт в `privacy.py` и в модели
заявки): CONTEXT.md разводит два термина, и одно другого не заменяет.

Практика РКН 2025-2026 (юр. ресёрч в `docs/research/`): cookie
и идентификаторы Метрики считаются персональными данными, пассивный
баннер «продолжая пользоваться сайтом» больше не защищает — нужно
активное действие посетителя, и до него счётчик не должен запускаться.

Поэтому решение принимает сервер, а не браузер: выбор лежит в cookie,
и пока там не «да», разметки Метрики в ответе просто нет. Такое
поведение проверяется обычным HTTP-тестом — в отличие от варианта,
где счётчик прячет JS уже после отдачи страницы.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.http import HttpRequest

COOKIE_NAME = "cookie_consent"
ACCEPTED = "yes"
DECLINED = "no"
# Год: столько сайт помнит выбор посетителя и не переспрашивает
MAX_AGE = 365 * 24 * 60 * 60


def accepted(request: HttpRequest) -> bool:
    """Посетитель нажал «Принять»."""
    return request.COOKIES.get(COOKIE_NAME) == ACCEPTED


def answered(request: HttpRequest) -> bool:
    """Посетитель уже сделал выбор — переспрашивать не нужно."""
    return request.COOKIES.get(COOKIE_NAME) in {ACCEPTED, DECLINED}


def banner(request: HttpRequest, *, has_counter: bool) -> dict[str, Any]:
    """Данные cookie-баннера: показывать ли его и чем отвечать.

    Имя cookie, её срок и значения ответов принадлежат этому модулю,
    поэтому и уезжают в разметку отсюда: `cookies.js` читает их
    из data-атрибутов баннера и своей копии не держит.
    """
    return {
        # Без счётчика спрашивать не о чем: сайт ставит только строго
        # необходимые cookie (CSRF, сессия, сам выбор)
        "needed": has_counter and not answered(request),
        "cookie": COOKIE_NAME,
        "accepted": ACCEPTED,
        "declined": DECLINED,
        "max_age": MAX_AGE,
    }
