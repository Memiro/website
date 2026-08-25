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

from tests.sources import site_css

COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
CLASS_IN_SELECTOR = re.compile(r"\.([a-z0-9-]+)", re.IGNORECASE)


class StylesheetError(Exception):
    """Скобки таблицы стилей не сходятся — разбирать нечего."""


UNCLOSED_RULE = "незакрытое правило"
UNCLOSED_AT_RULE = "незакрытый at-rule"
STRAY_BRACE = "лишняя закрывающая скобка"


class Rule(NamedTuple):
    """Одно правило: селектор целиком и объявления внутри скобок."""

    selector: str
    body: str
    # Правило пришло из `@media` (или другого блочного at-rule) и,
    # значит, действует не на любой ширине
    conditional: bool


def stylesheet() -> str:
    """Текст `site.css` без комментариев."""
    return COMMENT.sub("", site_css().read_text(encoding="utf-8"))


def rules(css: str) -> list[Rule]:
    """Все правила таблицы, включая вложенные в `@media`.

    Ошибиться разбор может только громко: `StylesheetError` на
    испорченном файле. Молчаливая ошибка здесь опаснее падения — тест
    на цену спрашивает, объявлено ли свойство безусловно, и лишний
    уровень вложенности сделал бы его зелёным на сломанной вёрстке.
    """
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
                # Блочный at-rule (`@media`, `@supports`): правила внутри
                # разбираются дальше, но помечаются условными
                depth += 1
            else:
                end = css.find("}", index)
                if end < 0:
                    unclosed = f"{UNCLOSED_RULE} `{selector}`"
                    raise StylesheetError(unclosed)
                body = css[index + 1 : end]
                found.append(Rule(selector, body, conditional=depth > 0))
                index = end
        elif char == "}":
            # Объявления блока дочитаны — что не стало правилом, тому
            # и не быть селектором. Без сброса тело `@font-face`,
            # вложенных правил не имеющего, приклеилось бы к следующему
            if depth == 0:
                raise StylesheetError(STRAY_BRACE)
            prelude = []
            depth -= 1
        elif char == ";":
            # At-rule на одной строке (`@import url(...);`) блока не
            # открывает. Прими его за блочный — и `depth` не вернётся
            # к нулю, а все правила файла станут условными
            prelude = []
        else:
            prelude.append(char)
        index += 1
    if depth:
        raise StylesheetError(UNCLOSED_AT_RULE)
    return found


def classes(selector: str) -> set[str]:
    """Классы селектора целиком: `.grid-4, .grid-3` — это оба.

    Из всего списка, а не только из последнего перед скобкой: иначе
    правило на два селектора прошло бы проверку молча.
    """
    return set(CLASS_IN_SELECTOR.findall(selector))
