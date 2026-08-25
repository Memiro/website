"""Страницы ошибок: свой вид, свой код ответа, без техинформации Django.

Проверка идёт запросами, а не вызовом представления: у 400, 403 и 500
маршрута не бывает вовсе, и именно проводка — `handler400`/`handler403`
в `urls.py`, карта переезда для 410 — та часть, которая ломается молча.
Поэтому каждому коду устроен настоящий цикл запроса при `DEBUG=False`:
с `DEBUG=True` Django отдаёт свою отладочную страницу и подмену шаблона
не заметил бы ни один assert.

Отдельно проверяется 500-я: её шаблон рисуется без `request`, значит
без контекст-процессоров и без базы — а упавшая база и есть самая
частая причина 500.
"""

from __future__ import annotations

import re
from http import HTTPStatus

import pytest
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.template import loader
from django.test import Client
from django.urls import path
from pytest_django.fixtures import Settings

from memiro.content.models import SiteContacts
from memiro.seo.models import LegacyUrl
from memiro.urls import handler400, handler403, handler404  # noqa: F401
from memiro.urls import urlpatterns as site_urls
from tests.cssrules import stylesheet
from tests.sources import templates_dir

# Телефон студии на 500-й стоит литералом: контактов из базы там взять
# неоткуда. Что он не разошёлся с админкой, сторожит отдельный тест
LITERAL_PHONE = "+7 981 230-40-50"

# Текст исключения: на странице ошибки его быть не должно
BOOM = "внутренности, которые покупателю не показывают"

# Любой шаблонный тег или переменная: 500-й нельзя ни то ни другое —
# ни `{{ contacts.phone }}` без контекст-процессоров, ни `{% url %}`
# с urlconf, который на этой странице сам может быть виновником
TEMPLATE_SYNTAX = re.compile(r"\{[{%]")
TEMPLATE_COMMENT = re.compile(r"\{#.*?#\}")

# Цвет в таблице стилей и в 500-й: `site.css` она подключить не может
HEX_COLOR = re.compile(r"#[0-9a-f]{6}\b", re.IGNORECASE)


def assert_offers_both_exits(content: str) -> None:
    """Поиска по сайту нет: выходы со страницы ошибки — ровно эти два."""
    assert "Каталог" in content
    assert "Контакты" in content


def falls(request: HttpRequest) -> HttpResponse:
    """Представление, которое всегда падает."""
    raise RuntimeError(BOOM)


def forbids(request: HttpRequest) -> HttpResponse:
    """Представление, которое всегда закрывает доступ."""
    raise PermissionDenied


# ROOT_URLCONF ищет `urlpatterns` и обработчики ошибок в модуле; для
# сквозных проверок 403 и 500 этим модулем на время теста становится сам
# файл теста. Маршруты витрины подмешиваются целиком: страница ошибки
# зовёт `{% url %}` каталога и «Контактов», и без них упала бы сама
urlpatterns = [path("boom/", falls), path("closed/", forbids), *site_urls]


@pytest.fixture
def live(settings: Settings) -> Settings:
    """Контур как в проде: отладочных страниц Django нет."""
    settings.DEBUG = False
    return settings


@pytest.mark.django_db
def test_bad_host_renders_the_error_page(
    client: Client, live: Settings
) -> None:
    """400 приходит из жизни чужим `Host` — и это самый частый его случай.

    Мета собирается теми же контекст-процессорами, а `canonical` спрашивал
    у запроса хост, которого нет: без оговорки в `seo.context_processors`
    страница 400 падала бы внутрь 500-й.
    """
    live.ALLOWED_HOSTS = ["testserver"]

    response = client.get("/", headers={"host": "chuzhoj.example"})
    content = response.content.decode()

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Некорректный запрос" in content
    assert_offers_both_exits(content)


@pytest.mark.django_db
def test_forbidden_view_renders_the_error_page(
    client: Client, live: Settings
) -> None:
    live.ROOT_URLCONF = __name__

    response = client.get("/closed/")
    content = response.content.decode()

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "Доступ закрыт" in content
    assert_offers_both_exits(content)


@pytest.mark.django_db
def test_unknown_address_renders_the_error_page(
    client: Client, live: Settings
) -> None:
    response = client.get("/net-takoj-stranicy/")
    content = response.content.decode()

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "Страница не найдена" in content
    assert_offers_both_exits(content)
    assert "Traceback" not in content


@pytest.mark.django_db
def test_removed_legacy_address_renders_the_gone_page(
    client: Client, live: Settings
) -> None:
    """410 из карты переезда — страница, а не пустое тело (тикет 12)."""
    LegacyUrl.objects.create(old_path="/2023/01/statya/")

    response = client.get("/2023/01/statya/")
    content = response.content.decode()

    assert response.status_code == HTTPStatus.GONE
    assert "Страница удалена" in content
    assert_offers_both_exits(content)


@pytest.mark.django_db
def test_falling_view_renders_the_error_page(
    client: Client, live: Settings
) -> None:
    live.ROOT_URLCONF = __name__
    client.raise_request_exception = False

    response = client.get("/boom/")
    content = response.content.decode()

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert LITERAL_PHONE in content
    assert BOOM not in content
    assert "Traceback" not in content


@pytest.mark.django_db
def test_stale_form_renders_the_error_page(live: Settings) -> None:
    """Провал CSRF идёт мимо `handler403` — у Django на него своё
    представление, и без `CSRF_FAILURE_VIEW` оно отдаёт английскую
    страницу с техническими подсказками.

    Заявки это не касается: её форма уходит в API и получает оттуда
    сообщение в JSON. А вот любой обычный POST витрины — касается.
    """
    strict = Client(enforce_csrf_checks=True)

    response = strict.post("/", {})
    content = response.content.decode()

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "Страница устарела" in content
    assert 'lang="ru"' in content
    assert "CSRF" not in content
    assert_offers_both_exits(content)


@pytest.mark.django_db
def test_error_pages_stay_out_of_the_index(
    client: Client, live: Settings
) -> None:
    """Код ответа держит страницу вне индекса, `noindex` — вторым рядом."""
    content = client.get("/net-takoj-stranicy/").content.decode()

    assert 'name="robots" content="noindex' in content
    assert 'rel="canonical"' not in content


def test_server_error_page_needs_no_database() -> None:
    """500-я рисуется без `request`: контекст-процессоров у неё нет.

    Проверка идёт без метки `django_db`: страница, которой нужна база,
    здесь и упадёт — ровно как в проде на упавшей базе.
    """
    content = loader.render_to_string("500.html")

    assert LITERAL_PHONE in content
    assert_offers_both_exits(content)


def test_server_error_template_asks_nothing_of_django() -> None:
    """Тег или переменная в 500-й — это база и urlconf, которых нет."""
    source = (templates_dir() / "500.html").read_text(encoding="utf-8")

    assert not TEMPLATE_SYNTAX.findall(TEMPLATE_COMMENT.sub("", source))


@pytest.mark.django_db
def test_literal_phone_matches_the_admin() -> None:
    """Литерал на 500-й — копия строки контактов, и копия не должна врать.

    Телефон правит владелец в админке (тикет 01); на 500-й он стоит
    литералом не по небрежности, а потому что базы там может не быть.
    Тест ловит расхождение, которого иначе никто не увидит.
    """
    assert SiteContacts.load().phone_display == LITERAL_PHONE


def test_server_error_page_keeps_the_palette() -> None:
    """Цвета 500-й — те же, что у витрины, хоть и переписаны в неё руками.

    Подключить `site.css` страница не может: она рисуется тогда, когда
    доверять нечему. Копия палитры — цена этой независимости, и цена
    честная ровно до тех пор, пока копия совпадает с оригиналом
    (ADR-0004: визуальный язык один на весь сайт).
    """
    source = (templates_dir() / "500.html").read_text(encoding="utf-8")
    site = stylesheet().lower()

    strayed = [
        color
        for color in HEX_COLOR.findall(source)
        if color.lower() not in site
    ]

    assert not strayed, "Цвета 500-й разошлись с `site.css`: " + ", ".join(
        strayed
    )
