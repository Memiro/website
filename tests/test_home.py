from http import HTTPStatus
from types import SimpleNamespace

import pytest
from django.test import Client

from memiro.catalog.models import Category, Product


@pytest.fixture
def showcase(db: None) -> SimpleNamespace:
    """Категория с популярными, акционным и черновым товарами."""
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    second = Product.objects.create(
        category=category,
        name="Grand Arc",
        slug="grand-arc",
        price=21500,
        is_published=True,
        is_popular=True,
        order=2,
    )
    first = Product.objects.create(
        category=category,
        name="Halo Moon",
        slug="halo-moon",
        price=11795,
        is_published=True,
        is_popular=True,
        order=1,
    )
    promo = Product.objects.create(
        category=category,
        name="Dew Glow",
        slug="dew-glow",
        price=7998,
        is_published=True,
        is_promo=True,
    )
    draft = Product.objects.create(
        category=category,
        name="Черновик",
        slug="draft",
        price=1000,
        is_popular=True,
        is_promo=True,
    )
    return SimpleNamespace(
        category=category,
        first=first,
        second=second,
        promo=promo,
        draft=draft,
    )


def test_home_responds_with_html(client: Client, db: None) -> None:
    """Главная отвечает и на пустой базе."""
    response = client.get("/")

    assert response.status_code == HTTPStatus.OK
    assert response["Content-Type"].startswith("text/html")
    assert "memiro" in response.content.decode()


def test_home_shows_hero_and_steps(client: Client, db: None) -> None:
    """Статические блоки макета: hero и «как оформить заявку»."""
    content = client.get("/").content.decode()

    assert "Зеркала, сделанные под ваш интерьер" in content
    assert "Как оформить заявку" in content


def test_home_shows_categories_from_db(
    client: Client, showcase: SimpleNamespace
) -> None:
    content = client.get("/").content.decode()

    assert showcase.category.name in content


def test_home_hides_category_without_published_products(
    client: Client, db: None
) -> None:
    Category.objects.create(name="Перегородки", slug="peregorodki")

    content = client.get("/").content.decode()

    assert "Перегородки" not in content


def test_home_popular_ordered_by_manual_order(
    client: Client, showcase: SimpleNamespace
) -> None:
    """Популярное — ручной флаг с порядком: order=1 раньше order=2."""
    content = client.get("/").content.decode()

    assert content.index("Halo Moon") < content.index("Grand Arc")


def test_home_shows_promo_products(
    client: Client, showcase: SimpleNamespace
) -> None:
    content = client.get("/").content.decode()

    assert "Dew Glow" in content


def test_home_hides_draft_products(
    client: Client, showcase: SimpleNamespace
) -> None:
    content = client.get("/").content.decode()

    assert "Черновик" not in content


def test_home_hides_empty_promo_and_popular_sections(
    client: Client, db: None
) -> None:
    """Без товаров в БД блоки «акция» и «популярное» не рисуются."""
    content = client.get("/").content.decode()

    assert "Популярное" not in content
    assert "Акция" not in content
