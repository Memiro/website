"""Плитка товара (тикет 10): фото, название, цена — и ничего больше.

Кнопки заявки на плитке нет: покупатель добавляет не строку каталога,
а конфигурацию — размер и полотно выбираются на карточке товара. Вся
плитка поэтому одна ссылка, и вести ей некуда, кроме товара.

Плитка собирается одним шаблоном `catalog/_card.html`, но включается
в четырёх местах, и проверяются все четыре: забытая кнопка осталась бы
ровно там, куда не заглянули.
"""

from __future__ import annotations

import re
from http import HTTPStatus
from types import SimpleNamespace

import pytest
from django.test import Client

from memiro.catalog.models import (
    Attribute,
    Category,
    Landing,
    LandingCondition,
    Product,
    ProductAttribute,
)
from tests.cssrules import classes, rules, stylesheet

CARD = re.compile(r'<article class="product-card">.*?</article>', re.DOTALL)
LINK = re.compile(r"<a\b")

# Классы, которыми была размечена нижняя строка плитки с кнопкой.
# Разметки под них больше нет, и правила в таблице стилей — мёртвые
GONE_FROM_STYLESHEET = frozenset({"card-actions", "cart-btn"})

# Отступ кольца фокуса внутрь элемента — отрицательный
OUTSIDE_OFFSET = re.compile(r"outline-offset\s*:\s*-")


@pytest.fixture
def shop(db: None) -> SimpleNamespace:
    """Категория с популярным товаром, посадочной и «похожими»."""
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    podsvetka = Attribute.objects.create(
        category=category,
        name="Подсветка",
        slug="podsvetka",
        kind=Attribute.Kind.BOOLEAN,
    )
    halo = Product.objects.create(
        category=category,
        name="Halo Moon",
        slug="halo-moon",
        price=11795,
        photo_small="products/small/halo.jpg",
        is_published=True,
        is_popular=True,
    )
    ProductAttribute.objects.create(
        product=halo, attribute=podsvetka, value_bool=True
    )
    view_match = Product.objects.create(
        category=category,
        name="View Match",
        slug="view-match",
        price=8352,
        is_published=True,
        is_popular=True,
    )
    ProductAttribute.objects.create(
        product=view_match, attribute=podsvetka, value_bool=True
    )
    landing = Landing.objects.create(
        category=category,
        slug="zerkala-s-podsvetkoy",
        title="Зеркала с подсветкой на заказ — memiro",
        heading="Зеркала с подсветкой",
        description="Зеркала с подсветкой на заказ в Санкт-Петербурге.",
        is_published=True,
    )
    LandingCondition.objects.create(
        landing=landing, attribute=podsvetka, value_bool=True
    )
    return SimpleNamespace(halo=halo, landing=landing)


def cards(client: Client, url: str) -> list[str]:
    response = client.get(url)
    assert response.status_code == HTTPStatus.OK
    found = CARD.findall(response.content.decode())
    assert found, f"на {url} нет ни одной плитки товара"
    return found


@pytest.fixture
def everywhere(client: Client, shop: SimpleNamespace) -> dict[str, list[str]]:
    """Плитки со всех четырёх страниц, где они показываются."""
    return {
        "категория": cards(client, "/catalog/zerkala/"),
        "посадочная": cards(client, shop.landing.get_absolute_url()),
        "главная": cards(client, "/"),
        "похожие": cards(client, "/catalog/zerkala/halo-moon/"),
    }


def test_tile_has_no_inquiry_button(everywhere: dict[str, list[str]]) -> None:
    """Заявка собирается на карточке товара, а не в списке."""
    for where, found in everywhere.items():
        for card in found:
            assert 'data-toggle="cart"' not in card, where
            assert "Добавить в заявку" not in card, where


def test_tile_is_a_single_link(everywhere: dict[str, list[str]]) -> None:
    """Плитка целиком ведёт на товар — вложенных ссылок в ней нет."""
    for where, found in everywhere.items():
        for card in found:
            assert len(LINK.findall(card)) == 1, where


def test_tile_keeps_photo_name_and_price(
    client: Client, shop: SimpleNamespace
) -> None:
    """Убрана кнопка, а не содержимое плитки."""
    card = next(
        found
        for found in cards(client, "/catalog/zerkala/")
        if shop.halo.name in found
    )

    assert shop.halo.photo_small.url in card
    # Узкий неразрывный пробел — тот самый разделитель, на котором цена
    # не рвётся (тикет 09): нормализовать его тут — перестать его сторожить
    assert "11\u202f795" in card


def test_focus_ring_of_the_tile_link_is_drawn_inside() -> None:
    """Кольцо фокуса не срезается краем плитки.

    Ссылка занимает плитку целиком, а `.product-card` скрывает всё, что
    вылезает за края. Общее кольцо лежит снаружи — и у клавиатуры пропало
    бы целиком, молча: вёрстка при этом выглядит нетронутой.
    """
    inside = [
        rule
        for rule in rules(stylesheet())
        if ".card-link:focus-visible" in rule.selector
        and OUTSIDE_OFFSET.search(rule.body)
    ]

    assert inside, (
        "у ссылки плитки нет `outline-offset` внутрь — кольцо фокуса "
        "срежет `overflow: hidden` у `.product-card`"
    )


def test_stylesheet_keeps_no_rules_for_the_gone_button() -> None:
    """Правила без разметки — след, по которому кнопку вернут обратно."""
    styled = {
        name for rule in rules(stylesheet()) for name in classes(rule.selector)
    }

    assert not GONE_FROM_STYLESHEET & styled, (
        "в `site.css` остались правила кнопки, которой на плитке нет: "
        + ", ".join(sorted(GONE_FROM_STYLESHEET & styled))
    )
