"""Абсолютный URL для метатегов — canonical и картинки OG.

Отдельным местом это стало из-за страниц ошибок. Хост вне
`ALLOWED_HOSTS` — это и есть 400, а её страница (`memiro/errors.py`)
собирается теми же контекст-процессорами и тегами, что остальные:
`build_absolute_uri` бросил бы `DisallowedHost` второй раз, уже внутри
шаблона ошибки, и покупатель вместо 400 получил бы 500.

Пусто вместо адреса — не потеря: печатают его canonical и OG, а запрос
с чужим хостом в индекс не идёт. `base.html` пустой тег и не выводит.

Разметка (`structured.py`), sitemap и robots строят URL сырым
`build_absolute_uri` и остаются как есть: до них запрос с чужим хостом
не доходит — он к этому моменту уже 400. На страницу ошибки разметка
поэтому и не ставится (`templates/errors/base.html`).
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
