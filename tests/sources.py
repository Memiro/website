"""Исходники витрины для тестов, которые читают их файлами.

Каталог шаблонов ищется одинаково уже в трёх тестах, и `cssrules.py`
завёл ту же оговорку про свою таблицу стилей: разбор живёт в одном
месте, чтобы четвёртый такой тест не переписывал его в четвёртый раз.

Список безданных страниц лежит здесь по той же причине: его завёл
`test_templates.py`, а `test_wording.py` обошёл бы те же страницы
своим списком — и разошёлся бы с ним на первой же новой странице.

`settings.TEMPLATES` тут не годится: он типизирован как `object` и mypy
его не индексирует. `STATICFILES_DIRS` — тот же `PACKAGE_DIR`, что
и `DIRS` у движка шаблонов.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings as django_settings

if TYPE_CHECKING:
    from pathlib import Path


# Страницы витрины, которым не нужны данные в базе: рендерятся
# на пустом каталоге
DATALESS_PAGES = (
    "/",
    "/about/",
    "/delivery/",
    "/privacy/",
    "/contacts/",
    "/works/",
    "/catalog/",
    "/cart/",
)


def templates_dir() -> Path:
    """Каталог шаблонов витрины."""
    return django_settings.STATICFILES_DIRS[0].parent / "templates"


def scripts_dir() -> Path:
    """Каталог скриптов витрины."""
    return django_settings.STATICFILES_DIRS[0] / "js"


def site_css() -> Path:
    """Таблица стилей витрины."""
    return django_settings.STATICFILES_DIRS[0] / "css" / "site.css"
