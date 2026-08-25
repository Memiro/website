"""Разбор `site.css` для структурных тестов вёрстки.

Тестов, которые читают таблицу стилей и что-то в ней требуют, уже два,
и правила они ищут одинаково. Разбор живёт здесь, чтобы третий такой
тест не переписывал его в третий раз.

Разбор линейный, а не регуляркой: важно, лежит ли правило внутри
`@media`. Регулярка вложенность не видит и отдаёт правило из
медиазапроса неотличимым от правила верхнего уровня — а требование
«так на любой ширине» на объявлении из `@media (max-width: 640px)`
проверять нельзя.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from django.conf import settings as django_settings

COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
CLASS_IN_SELECTOR = re.compile(r"\.([a-z0-9-]+)", re.IGNORECASE)


class Rule(NamedTuple):
    """Одно правило: селектор целиком и объявления внутри скобок."""

    selector: str
    body: str
    # Правило пришло из `@media` (или другого блочного at-rule) и,
    # значит, действует не на любой ширине
    conditional: bool


def stylesheet() -> str:
    """Текст `site.css` без комментариев.

    Каталог статики берётся из `STATICFILES_DIRS`: `settings.TEMPLATES`
    типизирован как `object` и mypy его не индексирует.
    """
    path = django_settings.STATICFILES_DIRS[0] / "css" / "site.css"
    return COMMENT.sub("", path.read_text(encoding="utf-8"))


def rules(css: str) -> list[Rule]:
    """Все правила таблицы, включая вложенные в `@media`."""
    found: list[Rule] = []
    prelude: list[str] = []
    depth = 0
    index = 0
    while index < len(css):
        char = css[index]
        if char == "{":
            selector = "".join(prelude).strip()
            prelude = []
            if selector.startswith("@"):
                # Блочный at-rule: правила внутри разбираются дальше
                depth += 1
            else:
                end = css.index("}", index)
                body = css[index + 1 : end]
                found.append(Rule(selector, body, conditional=depth > 0))
                index = end
        elif char == "}":
            depth -= 1
        else:
            prelude.append(char)
        index += 1
    return found


def classes(selector: str) -> set[str]:
    """Классы селектора целиком: `.grid-4, .grid-3` — это оба.

    Из всего списка, а не только из последнего перед скобкой: иначе
    правило на два селектора прошло бы проверку молча.
    """
    return set(CLASS_IN_SELECTOR.findall(selector))
