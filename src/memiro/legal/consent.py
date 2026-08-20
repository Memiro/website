"""Cookie-согласие на аналитику: счётчик не грузится, пока не разрешили.

Это не согласие на обработку ПД из формы заявки (то живёт
в `privacy.py` и в модели заявки): одно другого не заменяет.

Практика РКН 2025-2026 (юр. ресёрч в `docs/research/`): cookie
и идентификаторы Метрики считаются персональными данными,
пассивный баннер «продолжая пользоваться сайтом» больше не защищает —
нужно активное действие посетителя, и до него счётчик не должен
запускаться.

Поэтому решение принимает сервер, а не браузер: выбор лежит в cookie,
и пока там не «да», разметки Метрики в ответе просто нет. Такое
поведение проверяется обычным HTTP-тестом — в отличие от варианта,
где счётчик прячет JS уже после отдачи страницы.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
