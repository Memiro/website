"""Плитки витрины (тикет 14): источник — посадочные, а не категории."""

from __future__ import annotations

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

CATEGORY_TILE_HREF = 'href="/catalog/zerkala/"'


@pytest.fixture
def shop(db: None) -> SimpleNamespace:
    """Категория «Зеркала», товар с подсветкой и товар без неё."""
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
    )
    ProductAttribute.objects.create(
        product=halo, attribute=podsvetka, value_bool=True
    )
    plain = Product.objects.create(
        category=category,
        name="View Match",
        slug="view-match",
        price=8352,
        is_published=True,
    )
    ProductAttribute.objects.create(
        product=plain, attribute=podsvetka, value_bool=False
    )
    return SimpleNamespace(
        category=category, podsvetka=podsvetka, halo=halo, plain=plain
    )


def make_landing(
    shop: SimpleNamespace,
    *,
    slug: str = "zerkala-s-podsvetkoy",
    heading: str = "Зеркала с подсветкой",
    is_published: bool = True,
    cover: str = "",
) -> Landing:
    landing = Landing.objects.create(
        category=shop.category,
        slug=slug,
        title=f"{heading} на заказ — memiro",
        heading=heading,
        description=f"{heading} на заказ в Санкт-Петербурге.",
        cover=cover,
        is_published=is_published,
    )
    LandingCondition.objects.create(
        landing=landing, attribute=shop.podsvetka, value_bool=True
    )
    return landing


def page_html(client: Client, url: str) -> str:
    response = client.get(url)
    assert response.status_code == HTTPStatus.OK
    return response.content.decode()


# --- Главная ---------------------------------------------------------


def test_home_tiles_link_to_landings(
    client: Client, shop: SimpleNamespace
) -> None:
    """Плитка ведёт на ЧПУ посадочной, а не на query-фильтр."""
    landing = make_landing(shop)

    html = page_html(client, "/")

    assert f'href="{landing.get_absolute_url()}"' in html
    assert landing.heading in html


def test_home_tiles_skip_categories(
    client: Client, shop: SimpleNamespace
) -> None:
    """Категория плиткой больше не становится: она тип товара."""
    make_landing(shop)

    html = page_html(client, "/")

    assert CATEGORY_TILE_HREF not in html


def test_home_hides_tiles_without_landings(
    client: Client, shop: SimpleNamespace
) -> None:
    """Без посадочных блок плиток исчезает целиком."""
    html = page_html(client, "/")

    assert "cats-grid" not in html
    assert CATEGORY_TILE_HREF not in html


def test_home_hides_unpublished_landing(
    client: Client, shop: SimpleNamespace
) -> None:
    landing = make_landing(shop, is_published=False)

    html = page_html(client, "/")

    assert landing.get_absolute_url() not in html


def test_home_hides_landing_without_products(
    client: Client, shop: SimpleNamespace
) -> None:
    """Посадочная без товаров отдаёт 404 — ссылки на неё быть не должно."""
    shop.halo.is_published = False
    shop.halo.save()
    landing = make_landing(shop)

    html = page_html(client, "/")

    assert landing.get_absolute_url() not in html


def test_home_tile_cover_comes_from_admin_field(
    client: Client, shop: SimpleNamespace
) -> None:
    make_landing(shop, cover="landings/podsvetka.jpg")

    html = page_html(client, "/")

    assert "landings/podsvetka.jpg" in html


def test_home_tile_cover_falls_back_to_product_photo(
    client: Client, shop: SimpleNamespace
) -> None:
    """Без обложки в админке плитка берёт первый товар посадочной с фото."""
    make_landing(shop)

    html = page_html(client, "/")

    assert shop.halo.photo_small.url in html


# --- Корень каталога -------------------------------------------------


def test_catalog_root_shows_landing_tiles(
    client: Client, shop: SimpleNamespace
) -> None:
    """С посадочными корень каталога перестаёт редиректить."""
    landing = make_landing(shop)

    html = page_html(client, "/catalog/")

    assert f'href="{landing.get_absolute_url()}"' in html


def test_catalog_root_redirects_without_landings(
    client: Client, shop: SimpleNamespace
) -> None:
    """Пока посадочных нет, единственная категория забирает корень себе."""
    response = client.get("/catalog/")

    assert response.status_code == HTTPStatus.FOUND
    assert response.headers["Location"] == "/catalog/zerkala/"


def test_catalog_root_keeps_categories_beside_landings(
    client: Client, shop: SimpleNamespace
) -> None:
    """Вторая категория не теряет вход с корня из-за посадочных зеркал."""
    make_landing(shop)
    other = Category.objects.create(name="Перегородки", slug="peregorodki")
    Product.objects.create(
        category=other,
        name="Перегородка",
        slug="peregorodka",
        price=30000,
        is_published=True,
    )

    html = page_html(client, "/catalog/")

    assert CATEGORY_TILE_HREF in html
    assert 'href="/catalog/peregorodki/"' in html
