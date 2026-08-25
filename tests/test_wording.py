"""Витрина называет подборку заявкой (тикет 13).

Слов «корзина» и «заказ» покупатель не видит: оплаты нет, ничего
не резервируется, и обещать оформление заказа сайт не вправе
(`CONTEXT.md`, «Подборка», «Заявка»). Внутренние имена —
`Inquiry.Source.CART`, `data-toggle="cart"`, адрес `/cart/` — под запрет
не попадают: это код, а старые заявки помнят свой источник.

Проверяется отданное, а не исходники: комментарий в шаблоне покупателю
не показывается и вправе называть вещи их кодовыми именами. Смотрим
и текст страницы, и подписи для чтеца (`title`, `aria-label`, `alt`):
произнесённое вслух — та же витрина. Строковые литералы скриптов
проверяются отдельно — их текст доезжает до страницы мимо шаблонов.
"""

from __future__ import annotations

import re
from http import HTTPStatus

import pytest
from django.test import Client

from memiro.catalog.models import Category, Product
from tests.sources import DATALESS_PAGES, static_dir, templates_dir

CATEGORY_URL = "/catalog/zerkala/"
PRODUCT_URL = "/catalog/zerkala/halo-moon/"

# «Корзина» запрещена целиком, «заказ» — только в смысле оформления:
# зеркала делаются на заказ, и это слово с витрины не уходит
BANNED = (
    re.compile(r"корзин", re.IGNORECASE),
    re.compile(r"оформ\w*\s+заказ", re.IGNORECASE),
    re.compile(r"ваш\w*\s+заказ", re.IGNORECASE),
    re.compile(r"чекаут|checkout", re.IGNORECASE),
)

# Скрипты и стили — не текст страницы: их разбирает `test_scripts…`
# по файлам, а разметка страницы иначе тащила бы их целиком
CODE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
)
TAG = re.compile(r"<[^>]*>")
# Подписи, которые произносит чтец: тегом они срезаются вместе с ним
SPOKEN = re.compile(r'\b(?:title|aria-label|alt)="([^"]*)"', re.IGNORECASE)

# Видимый текст скриптов лежит и в кавычках, и в бэктиках: подстановку
# `${…}` держит именно шаблонный литерал, а вокруг неё — те же слова
LITERALS = (
    re.compile(r'"((?:[^"\\\n]|\\.)*)"'),
    re.compile(r"`((?:[^`\\]|\\.)*)`"),
)


def spoken(html: str) -> str:
    """Всё, что покупатель прочитает или услышит от чтеца."""
    body = CODE.sub(" ", html)
    return f"{TAG.sub(' ', body)} {' '.join(SPOKEN.findall(body))}"


def banned_in(text: str) -> list[str]:
    return [
        match.group(0)
        for pattern in BANNED
        for match in pattern.finditer(text)
    ]


@pytest.fixture
def product(db: None) -> Product:
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    return Product.objects.create(
        category=category,
        name="Halo Moon",
        slug="halo-moon",
        price=11795,
        is_published=True,
    )


@pytest.mark.django_db
@pytest.mark.parametrize("url", DATALESS_PAGES)
def test_pages_never_say_cart_or_order(client: Client, url: str) -> None:
    """Ни одна страница витрины не называет подборку корзиной."""
    response = client.get(url)

    assert response.status_code == HTTPStatus.OK
    found = banned_in(spoken(response.content.decode()))
    assert not found, f"{url}: {found}"


@pytest.mark.django_db
@pytest.mark.parametrize("url", [CATEGORY_URL, PRODUCT_URL])
@pytest.mark.usefixtures("product")
def test_catalog_pages_never_say_cart(client: Client, url: str) -> None:
    """Категория и карточка — тоже витрина, и данные им нужны."""
    response = client.get(url)

    assert response.status_code == HTTPStatus.OK
    found = banned_in(spoken(response.content.decode()))
    assert not found, f"{url}: {found}"


def test_scripts_never_say_cart() -> None:
    """Текст, который скрипт печатает на странице, — та же витрина."""
    scripts = sorted((static_dir() / "js").glob("*.js"))
    assert scripts, "скриптов витрины не нашлось — тест смотрит не туда"

    leaking = [
        f"{path.name}: {found}"
        for path in scripts
        for literal in LITERALS
        for match in literal.finditer(path.read_text(encoding="utf-8"))
        if (found := banned_in(match.group(1)))
    ]

    assert not leaking, leaking


@pytest.mark.django_db
@pytest.mark.usefixtures("product")
def test_add_button_invites_to_inquiry(client: Client) -> None:
    """Кнопка на карточке зовёт в заявку — в обоих своих состояниях."""
    card = client.get(PRODUCT_URL).content.decode()

    assert 'data-label-off="Добавить в заявку"' in card
    assert 'data-label-on="Добавлено в заявку"' in card


@pytest.mark.django_db
def test_header_icon_counts_inquiry_items(client: Client) -> None:
    """Тележка обещала бы магазин: в шапке список со счётчиком позиций."""
    page = client.get("/").content.decode()

    assert 'aria-label="Заявка"' in page
    assert 'data-count="cart"' in page


def test_no_trolley_icon_is_left() -> None:
    """Иконку зовут по тому, что она рисует, — тележки среди них нет."""
    icons = templates_dir() / "icons"

    assert not (icons / "cart.svg").exists()
    assert (icons / "inquiry.svg").exists()
