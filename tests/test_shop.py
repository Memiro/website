import re
from http import HTTPStatus

import pytest
from django.test import Client

from memiro.catalog.models import Category, Product

HALO_PRICE = 11795
VIEW_MATCH_PRICE = 8300


@pytest.fixture
def products(db: None) -> list[Product]:
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    return [
        Product.objects.create(
            category=category,
            name=name,
            slug=slug,
            price=price,
            is_published=published,
        )
        for name, slug, price, published in (
            ("Halo Moon", "halo-moon", HALO_PRICE, True),
            ("View Match", "view-match", VIEW_MATCH_PRICE, True),
            ("Черновик", "draft", 5000, False),
        )
    ]


@pytest.mark.django_db
def test_summaries_return_requested_products(
    client: Client, products: list[Product]
) -> None:
    """Подборка подтягивает названия и цены с сервера."""
    ids = f"{products[1].pk},{products[0].pk}"

    response = client.get(f"/api/products?ids={ids}")

    assert response.status_code == HTTPStatus.OK
    items = response.json()["items"]
    assert [item["name"] for item in items] == ["View Match", "Halo Moon"]
    assert items[0]["price"] == VIEW_MATCH_PRICE
    assert items[0]["url"] == "/catalog/zerkala/view-match/"


@pytest.mark.django_db
def test_summaries_skip_unpublished(
    client: Client, products: list[Product]
) -> None:
    """Снятый с публикации товар исчезает из подборки, а не ломает её."""
    ids = f"{products[2].pk},{products[0].pk}"

    response = client.get(f"/api/products?ids={ids}")

    assert response.status_code == HTTPStatus.OK
    assert [item["id"] for item in response.json()["items"]] == [
        products[0].pk
    ]


@pytest.mark.django_db
def test_summaries_without_ids_are_empty(client: Client) -> None:
    """Пустая подборка не требует особого случая на клиенте."""
    response = client.get("/api/products?ids=")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["items"] == []


@pytest.mark.django_db
def test_summaries_reject_garbage_ids(client: Client) -> None:
    """Мусор в параметре — ошибка валидации, а не 500."""
    response = client.get("/api/products?ids=abc")

    assert response.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.django_db
def test_summaries_reject_oversized_selection(client: Client) -> None:
    """Подборка не бесконечна: длинный список отбивается явной ошибкой."""
    ids = ",".join(str(number) for number in range(1, 202))

    response = client.get(f"/api/products?ids={ids}")

    assert response.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.django_db
def test_cart_page_opens(client: Client) -> None:
    """Страница заявки отдаётся пустой; наполняет её клиент."""
    response = client.get("/cart/")

    assert response.status_code == HTTPStatus.OK


@pytest.mark.django_db
def test_favorites_page_is_gone(client: Client) -> None:
    """Избранного на сайте нет: адрес не отвечает и никуда не ведёт.

    Редиректа здесь быть не должно (тикет 04): сайт не запущен, этого
    адреса никто не видел, и переезжать посетителю неоткуда.
    """
    response = client.get("/favorites/")

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/cart/", "/"])
@pytest.mark.usefixtures("products")
def test_consent_checkbox_is_separate_and_unchecked(
    client: Client, url: str
) -> None:
    """Чекбокс согласия — отдельный и непредотмеченный на каждой форме."""
    body = client.get(url).content.decode()

    checkbox = next(
        tag
        for tag in re.findall(r"<input[^>]*>", body)
        if 'name="consent"' in tag
    )
    assert 'type="checkbox"' in checkbox
    assert "checked" not in checkbox


@pytest.mark.django_db
def test_home_has_inquiry_form(client: Client) -> None:
    """Форма заявки живёт и на главной."""
    body = client.get("/").content.decode()

    assert 'id="inquiry"' in body
    assert 'name="consent"' in body


@pytest.mark.django_db
def test_pages_expose_selection_limits(client: Client) -> None:
    """Границы подборки уезжают в браузер с сервера, а не копией в JS."""
    body = client.get("/").content.decode()

    assert '"max_items": 100' in body
    assert '"min_phone_digits": 7' in body


@pytest.mark.django_db
@pytest.mark.usefixtures("products")
def test_the_card_asks_for_a_wish_next_to_the_button(
    client: Client,
) -> None:
    """Пожелание вводится там же, где зеркало кладут в заявку.

    Поле названо товаром: своё пожелание у каждого зеркала, и чужая
    кнопка на той же странице его не подхватит (тикет 15).
    """
    product = Product.objects.get(slug="halo-moon")

    card = client.get("/catalog/zerkala/halo-moon/").content.decode()

    assert f'data-wish="{product.pk}"' in card
    assert 'maxlength="500"' in card


@pytest.mark.django_db
def test_the_inquiry_page_keeps_no_common_comment(client: Client) -> None:
    """На странице заявки общего поля нет: пожелание у каждой позиции.

    Поле модели остаётся — свободной форме с главной, где товара нет
    вовсе, писать больше негде (тикет 15).
    """
    page = client.get("/cart/").content.decode()
    home = client.get("/").content.decode()

    assert 'name="comment"' not in page
    assert 'name="comment"' in home


@pytest.mark.django_db
def test_pages_expose_the_wish_limit(client: Client) -> None:
    """Потолок пожелания приезжает в браузер с сервера, а не копией."""
    body = client.get("/").content.decode()

    assert '"max_wish_length": 500' in body
