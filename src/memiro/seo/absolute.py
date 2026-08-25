"""Абсолютный URL страницы — один вызов на всю витрину.

Отдельным местом это стало из-за страниц ошибок. Хост вне
`ALLOWED_HOSTS` — это и есть 400, а её страница (`memiro/errors.py`)
собирается теми же контекст-процессорами и тегами, что остальные:
`build_absolute_uri` бросил бы `DisallowedHost` второй раз, уже внутри
шаблона ошибки, и покупатель вместо 400 получил бы 500.

Пусто вместо адреса — не потеря: печатают его canonical и OG, а запрос
с чужим хостом в индекс не идёт. `base.html` пустой тег и не выводит.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import DisallowedHost

if TYPE_CHECKING:
    from django.http import HttpRequest


def absolute_uri(request: HttpRequest, path: str) -> str:
    """Абсолютный URL пути — или пусто, если хоста у запроса нет."""
    try:
        return str(request.build_absolute_uri(path))
    except DisallowedHost:
        return ""
