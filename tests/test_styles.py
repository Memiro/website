"""Боковые поля витрины держит один контейнер — `.wrap`.

`.wrap` задаёт `padding: 0 var(--pad)`. Любой класс, стоящий в разметке
рядом с ним, объявлен ниже по файлу и с той же специфичностью, поэтому
шорткат `padding: 26px 0` у соседа затирает боковые поля целиком —
и блок ложится вплотную к краю экрана. На широком экране это незаметно:
поля там даёт центрирование `max-width`, и ошибка вылезает только
ниже 1320px. Так молча разъехались футер, шапка каталога, панель
сортировки, тёмный блок и полоса преимуществ.

Соседи `.wrap` обязаны задавать вертикальные поля longhand-свойствами.
"""

from __future__ import annotations

import re

from tests.cssrules import classes, rules, stylesheet
from tests.sources import templates_dir

# `class="wrap footer-grid"` и прочие соседи по одному атрибуту.
# Кавычки любые: Django-шаблоны допускают и одинарные
CLASS_ATTR = re.compile(r"""class=["']([^"']*\bwrap\b[^"']*)["']""")
# `padding: 26px 0` — шорткат; `padding-top` под него не подходит
PADDING_SHORTHAND = re.compile(r"(?<!-)\bpadding\s*:")


def wrap_companions() -> set[str]:
    """Классы, которые в разметке стоят в одном атрибуте с `wrap`."""
    templates = templates_dir()
    return {
        name
        for path in templates.rglob("*.html")
        for attr in CLASS_ATTR.findall(path.read_text(encoding="utf-8"))
        for name in attr.split()
        if name != "wrap"
    }


def test_wrap_companions_keep_side_padding() -> None:
    companions = wrap_companions()

    offenders = [
        f"{rule.selector} {{{rule.body.strip()[:60]}…}}"
        for rule in rules(stylesheet())
        if PADDING_SHORTHAND.search(rule.body)
        and companions & classes(rule.selector)
    ]

    assert not offenders, (
        "Шорткат `padding` затирает боковые поля из `.wrap` — задайте "
        "padding-top/padding-bottom: " + "; ".join(offenders)
    )
