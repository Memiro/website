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

from django.conf import settings as django_settings

# `class="wrap footer-grid"` и прочие соседи по одному атрибуту.
# Кавычки любые: Django-шаблоны допускают и одинарные
CLASS_ATTR = re.compile(r"""class=["']([^"']*\bwrap\b[^"']*)["']""")
# Селектор правила целиком: `.footer-grid {` и `.grid-4, .grid-3 {`.
# Классы вынимаются из всего списка — иначе проверялся бы только
# последний перед скобкой, и правило на два селектора прошло бы молча
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
CLASS_IN_SELECTOR = re.compile(r"\.([a-z0-9-]+)", re.IGNORECASE)
# `padding: 26px 0` — шорткат; `padding-top` под него не подходит
PADDING_SHORTHAND = re.compile(r"(?<!-)\bpadding\s*:")


def wrap_companions() -> set[str]:
    """Классы, которые в разметке стоят в одном атрибуте с `wrap`."""
    # Каталог шаблонов берётся рядом со статикой: `settings.TEMPLATES`
    # типизирован как `object` и mypy его не индексирует, а `STATICFILES_DIRS`
    # — тот же `PACKAGE_DIR`, что и `DIRS` у движка шаблонов
    templates = django_settings.STATICFILES_DIRS[0].parent / "templates"
    return {
        name
        for path in templates.rglob("*.html")
        for attr in CLASS_ATTR.findall(path.read_text(encoding="utf-8"))
        for name in attr.split()
        if name != "wrap"
    }


def test_wrap_companions_keep_side_padding() -> None:
    companions = wrap_companions()
    stylesheet = django_settings.STATICFILES_DIRS[0] / "css" / "site.css"
    css = stylesheet.read_text(encoding="utf-8")

    offenders = [
        f"{selector.strip()} {{{body.strip()[:60]}…}}"
        for selector, body in RULE.findall(css)
        if PADDING_SHORTHAND.search(body)
        and companions & set(CLASS_IN_SELECTOR.findall(selector))
    ]

    assert not offenders, (
        "Шорткат `padding` затирает боковые поля из `.wrap` — задайте "
        "padding-top/padding-bottom: " + "; ".join(offenders)
    )
