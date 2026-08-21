"""Шаблоны не должны протекать своим синтаксисом на витрину.

Django считает комментарием `{# ... #}` только в пределах одной строки:
его лексер ищет теги регуляркой без `re.DOTALL`. Многострочный `{# ... #}`
тегом не признаётся и печатается покупателю как обычный текст. Ошибка
невидима для остальных тестов — страница отдаёт 200 и содержит всё, что
они ищут, — поэтому проверяется отдельно и с двух сторон: по исходникам
шаблонов и по тому, что сервер реально отдал.
"""

from __future__ import annotations

import re
from http import HTTPStatus
from pathlib import Path

import pytest
from django.test import Client

import memiro

TEMPLATES = Path(memiro.__file__).parent / "templates"

COMMENT = re.compile(r"\{#.*?#\}", re.DOTALL)

# Страницы, которым не нужны данные в базе: рендерятся на пустом каталоге
DATALESS_PAGES = (
    "/",
    "/about/",
    "/delivery/",
    "/privacy/",
    "/contacts/",
    "/works/",
    "/catalog/",
    "/cart/",
    "/favorites/",
)


def test_no_multiline_django_comments() -> None:
    """Многострочный `{# #}` — не комментарий, а текст на странице."""
    leaking = [
        f"{path.relative_to(TEMPLATES)}: {match.group(0)[:60]}…"
        for path in sorted(TEMPLATES.rglob("*.html"))
        for match in COMMENT.finditer(path.read_text())
        if "\n" in match.group(0)
    ]

    assert not leaking, (
        "Многострочные комментарии печатаются на витрине; "
        "переведите их на {% comment %}: " + "; ".join(leaking)
    )


@pytest.mark.django_db
@pytest.mark.parametrize("url", DATALESS_PAGES)
def test_page_renders_without_template_syntax(
    client: Client, url: str
) -> None:
    """В отданном HTML не остаётся ни комментариев, ни неразобранных тегов."""
    response = client.get(url)
    content = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert "{#" not in content
    assert "{%" not in content
    assert "{{" not in content
