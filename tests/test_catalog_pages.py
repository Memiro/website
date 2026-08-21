import re
from http import HTTPStatus
from types import SimpleNamespace

import pytest
from django.http import QueryDict
from django.test import Client

from memiro.catalog.filters import CatalogFilters
from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    Product,
    ProductAttribute,
    ProductImage,
)
from memiro.catalog.views import PAGE_SIZE


@pytest.fixture
def shop(db: None) -> SimpleNamespace:
    """Категория «Зеркала»: атрибуты форма/подсветка, два товара и черновик.

    Halo Moon — круглое с подсветкой, акция; View Match — прямоугольное
    без подсветки и дешевле.
    """
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    forma = Attribute.objects.create(
        category=category,
        name="Форма",
        slug="forma",
        kind=Attribute.Kind.CHOICE,
    )
    krugloe = AttributeValue.objects.create(attribute=forma, value="Круглое")
    priamougolnoe = AttributeValue.objects.create(
        attribute=forma, value="Прямоугольное"
    )
    podsvetka = Attribute.objects.create(
        category=category,
        name="Подсветка",
        slug="podsvetka",
        kind=Attribute.Kind.BOOLEAN,
        order=1,
    )
    halo = Product.objects.create(
        category=category,
        name="Halo Moon",
        slug="halo-moon",
        price=11795,
        article="2850",
        is_published=True,
        is_promo=True,
    )
    ProductAttribute.objects.create(
        product=halo, attribute=forma, value_option=krugloe
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
    )
    ProductAttribute.objects.create(
        product=view_match, attribute=forma, value_option=priamougolnoe
    )
    ProductAttribute.objects.create(
        product=view_match, attribute=podsvetka, value_bool=False
    )
    Product.objects.create(
        category=category, name="Черновик", slug="draft", price=1000
    )
    return SimpleNamespace(
        category=category,
        forma=forma,
        krugloe=krugloe,
        priamougolnoe=priamougolnoe,
        podsvetka=podsvetka,
        halo=halo,
        view_match=view_match,
    )


def page_html(client: Client, url: str) -> str:
    response = client.get(url)
    assert response.status_code == HTTPStatus.OK
    return response.content.decode()


MAIN_PHOTO_AND_ONE_SHOT = 2


def buttons(html: str) -> list[str]:
    """Открывающие теги кнопок: нужную ищем по атрибуту, а не по позиции."""
    return re.findall(r"<button[^>]*>", html)


def test_catalog_root_redirects_to_only_category(
    client: Client, shop: SimpleNamespace
) -> None:
    """С единственной видимой категорией /catalog/ ведёт сразу в неё."""
    response = client.get("/catalog/")

    assert response.status_code == HTTPStatus.FOUND
    assert response.headers["Location"] == "/catalog/zerkala/"


def test_catalog_root_lists_categories(
    client: Client, shop: SimpleNamespace
) -> None:
    """С несколькими видимыми категориями /catalog/ показывает список."""
    other = Category.objects.create(name="Перегородки", slug="peregorodki")
    Product.objects.create(
        category=other,
        name="Перегородка",
        slug="p",
        price=30000,
        is_published=True,
    )

    html = page_html(client, "/catalog/")

    assert "/catalog/zerkala/" in html
    assert "/catalog/peregorodki/" in html


def test_category_page_shows_published_products_only(
    client: Client, shop: SimpleNamespace
) -> None:
    html = page_html(client, "/catalog/zerkala/")

    assert "Halo Moon" in html
    assert "View Match" in html
    assert "Черновик" not in html


def test_category_without_published_products_404(
    client: Client, shop: SimpleNamespace
) -> None:
    """Категория без опубликованных товаров не видна на витрине."""
    Category.objects.create(name="Пустая", slug="pustaia")

    response = client.get("/catalog/pustaia/")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_choice_filter_narrows(client: Client, shop: SimpleNamespace) -> None:
    html = page_html(client, f"/catalog/zerkala/?forma={shop.krugloe.pk}")

    assert "Halo Moon" in html
    assert "View Match" not in html


def test_choice_filter_or_within_attribute(
    client: Client, shop: SimpleNamespace
) -> None:
    """Значения одного атрибута объединяются по ИЛИ."""
    html = page_html(
        client,
        f"/catalog/zerkala/?forma={shop.krugloe.pk}"
        f"&forma={shop.priamougolnoe.pk}",
    )

    assert "Halo Moon" in html
    assert "View Match" in html


def test_filters_and_between_attributes(
    client: Client, shop: SimpleNamespace
) -> None:
    """Разные атрибуты объединяются по И."""
    html = page_html(
        client,
        f"/catalog/zerkala/?forma={shop.krugloe.pk}&podsvetka=1",
    )

    assert "Halo Moon" in html
    assert "View Match" not in html


def test_boolean_filter_narrows(client: Client, shop: SimpleNamespace) -> None:
    html = page_html(client, "/catalog/zerkala/?podsvetka=0")

    assert "View Match" in html
    assert "Halo Moon" not in html


def test_empty_filter_combination_404(
    client: Client, shop: SimpleNamespace
) -> None:
    """Комбинация фильтров без товаров — страницы нет."""
    response = client.get(
        f"/catalog/zerkala/?forma={shop.krugloe.pk}&podsvetka=0"
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("token", ["999999", "abc"])
def test_garbage_filter_value_404(
    client: Client, shop: SimpleNamespace, token: str
) -> None:
    response = client.get(f"/catalog/zerkala/?forma={token}")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_unrelated_query_params_ignored(
    client: Client, shop: SimpleNamespace
) -> None:
    """Посторонние параметры (utm и прочее) не роняют страницу."""
    html = page_html(client, "/catalog/zerkala/?utm_source=ads")

    assert "Halo Moon" in html


def test_applied_filters_block(client: Client, shop: SimpleNamespace) -> None:
    with_filter = page_html(
        client, f"/catalog/zerkala/?forma={shop.krugloe.pk}"
    )
    without_filter = page_html(client, "/catalog/zerkala/")

    assert "Сбросить всё" in with_filter
    assert "Форма: Круглое" in with_filter
    assert "Сбросить всё" not in without_filter


def test_counts_exclude_own_attribute_selection(
    shop: SimpleNamespace,
) -> None:
    """Счётчик значения не сужается выбором в своей же группе."""
    base = shop.category.products.filter(is_published=True)
    filters = CatalogFilters.parse(shop.category, QueryDict("podsvetka=1"))

    groups = {
        group.attribute.slug: {
            option.label: option.count for option in group.options
        }
        for group in filters.groups(base)
    }

    assert groups["forma"] == {"Круглое": 1, "Прямоугольное": 0}
    assert groups["podsvetka"] == {"да": 1, "нет": 1}


# --- Диапазон цены (тикет 13) ----------------------------------------


@pytest.mark.parametrize(
    ("query", "shown", "hidden"),
    [
        ("price_max=9000", "View Match", "Halo Moon"),
        ("price_min=9000", "Halo Moon", "View Match"),
    ],
)
def test_price_bound_narrows(
    client: Client,
    shop: SimpleNamespace,
    query: str,
    shown: str,
    hidden: str,
) -> None:
    """Halo Moon стоит 11795 ₽, View Match — 8352 ₽."""
    html = page_html(client, f"/catalog/zerkala/?{query}")

    assert shown in html
    assert hidden not in html


def test_price_bounds_are_inclusive(
    client: Client, shop: SimpleNamespace
) -> None:
    """Товар с ценой ровно на границе из выдачи не выпадает."""
    html = page_html(client, "/catalog/zerkala/?price_min=8352&price_max=8352")

    assert "View Match" in html
    assert "Halo Moon" not in html


def test_price_combines_with_attribute_filter(
    client: Client, shop: SimpleNamespace
) -> None:
    """Диапазон цены и фильтры атрибутов объединяются по И."""
    html = page_html(
        client, f"/catalog/zerkala/?forma={shop.krugloe.pk}&price_min=9000"
    )

    assert "Halo Moon" in html
    assert "View Match" not in html


def test_empty_price_combination_404(
    client: Client, shop: SimpleNamespace
) -> None:
    """Комбинация «фильтр + цена» без товаров ведёт себя как пустая."""
    response = client.get(
        f"/catalog/zerkala/?forma={shop.krugloe.pk}&price_max=9000"
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    "query",
    [
        "price_min=abc",
        "price_max=-5",
        # Незначащий ноль и второй такой же параметр дали бы чип,
        # крестик которого снимает не ту границу
        "price_min=08352",
        "price_min=1000&price_min=9000",
    ],
)
def test_garbage_price_404(
    client: Client, shop: SimpleNamespace, query: str
) -> None:
    """Цена, записанная не одним каноничным числом, — страницы нет."""
    response = client.get(f"/catalog/zerkala/?{query}")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_price_chip_removes_only_its_bound(
    client: Client, shop: SimpleNamespace
) -> None:
    """Крестик у чипа цены убирает свою границу, вторую оставляет."""
    html = page_html(client, "/catalog/zerkala/?price_min=1000&price_max=9000")

    assert "Цена от 1 000 ₽" in html
    assert "Цена до 9 000 ₽" in html
    assert "?price_max=9000" in html
    assert "?price_min=1000" in html


def test_price_control_bounds_come_from_products(
    client: Client, shop: SimpleNamespace
) -> None:
    """Границы — самый дешёвый и самый дорогой опубликованный товар."""
    html = page_html(client, "/catalog/zerkala/")

    assert 'name="price_min"' in html
    assert 'placeholder="8352"' in html
    assert 'placeholder="11795"' in html
    # Черновик за 1000 ₽ границу не двигает
    assert 'placeholder="1000"' not in html


def test_price_control_hidden_for_single_price(
    client: Client, shop: SimpleNamespace
) -> None:
    """Сужать нечего, когда все товары категории стоят одинаково."""
    Product.objects.filter(pk=shop.halo.pk).update(price=shop.view_match.price)

    html = page_html(client, "/catalog/zerkala/")

    assert 'name="price_min"' not in html


def test_counts_respect_price_range(shop: SimpleNamespace) -> None:
    """Цена группой не является — она сужает счётчики всех групп."""
    base = shop.category.products.filter(is_published=True)
    filters = CatalogFilters.parse(
        shop.category, QueryDict("podsvetka=0&price_max=9000")
    )

    groups = {
        group.attribute.slug: {
            option.label: option.count for option in group.options
        }
        for group in filters.groups(base)
    }

    assert groups["forma"] == {"Круглое": 0, "Прямоугольное": 1}
    # Без ограничения по цене у «да» был бы Halo Moon за 11795 ₽
    assert groups["podsvetka"] == {"да": 0, "нет": 1}


def test_price_filtered_page_canonical_points_to_category(
    client: Client, shop: SimpleNamespace
) -> None:
    """Цена — такой же параметрический дубль, как прочие фильтры."""
    html = page_html(client, "/catalog/zerkala/?price_max=11795")

    assert (
        '<link rel="canonical" href="http://testserver/catalog/zerkala/">'
        in html
    )


def test_sort_by_price_ascending(
    client: Client, shop: SimpleNamespace
) -> None:
    html = page_html(client, "/catalog/zerkala/?sort=price")

    assert html.index("View Match") < html.index("Halo Moon")


def test_sort_by_price_descending(
    client: Client, shop: SimpleNamespace
) -> None:
    html = page_html(client, "/catalog/zerkala/?sort=-price")

    assert html.index("Halo Moon") < html.index("View Match")


def test_filtered_page_canonical_points_to_category(
    client: Client, shop: SimpleNamespace
) -> None:
    """Фасетные URL не индексируются — canonical на категорию (ADR-0003)."""
    html = page_html(
        client, f"/catalog/zerkala/?forma={shop.krugloe.pk}&sort=price"
    )

    assert (
        '<link rel="canonical" href="http://testserver/catalog/zerkala/">'
        in html
    )


@pytest.fixture
def paged_category(db: None) -> Category:
    """Категория на 13 товаров — две страницы при размере страницы 12."""
    category = Category.objects.create(name="Много", slug="mnogo")
    for number in range(1, 14):
        Product.objects.create(
            category=category,
            name=f"Товар {number:02d}",
            slug=f"tovar-{number:02d}",
            price=1000 + number,
            is_published=True,
            order=number,
        )
    return category


def test_pagination_pages_and_self_canonical(
    client: Client, paged_category: Category
) -> None:
    first = page_html(client, "/catalog/mnogo/")
    second = page_html(client, "/catalog/mnogo/?page=2")

    assert first.count('class="product-card"') == PAGE_SIZE
    assert second.count('class="product-card"') == 1
    assert "Товар 13" in second
    assert (
        '<link rel="canonical" href="http://testserver/catalog/mnogo/">'
        in first
    )
    assert (
        '<link rel="canonical" '
        'href="http://testserver/catalog/mnogo/?page=2">' in second
    )


def test_pagination_out_of_range_404(
    client: Client, paged_category: Category
) -> None:
    response = client.get("/catalog/mnogo/?page=3")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_show_more_leads_to_next_page(
    client: Client, paged_category: Category
) -> None:
    """«Показать ещё» — обычная ссылка на ?page=n+1."""
    first = page_html(client, "/catalog/mnogo/")
    second = page_html(client, "/catalog/mnogo/?page=2")

    assert 'data-show-more href="?page=2"' in first
    assert "data-show-more" not in second


def test_product_page_shows_card_data(
    client: Client, shop: SimpleNamespace
) -> None:
    html = page_html(client, "/catalog/zerkala/halo-moon/")

    assert "Halo Moon" in html
    assert "11 795" in html
    assert "Круглое" in html
    assert "2850" in html
    assert "Акция" in html


def test_product_page_has_no_stock_state(
    client: Client, shop: SimpleNamespace
) -> None:
    """Понятия «в наличии» нет — всё под заказ (CONTEXT.md)."""
    html = page_html(client, "/catalog/zerkala/halo-moon/")

    assert "в наличии" not in html


def test_gallery_thumb_announces_selected_frame(
    client: Client, shop: SimpleNamespace
) -> None:
    """Выбранный кадр отмечен не только классом: читалке нужен aria-pressed."""
    Product.objects.filter(pk=shop.halo.pk).update(
        photo_large="products/large/halo.jpg"
    )
    ProductImage.objects.create(
        product=shop.halo, image="products/gallery/halo-2.jpg"
    )

    html = page_html(client, "/catalog/zerkala/halo-moon/")

    thumbs = [tag for tag in buttons(html) if "data-src=" in tag]
    pressed = [tag for tag in thumbs if 'aria-pressed="true"' in tag]

    # Главный кадр плюс один кадр галереи
    assert len(thumbs) == MAIN_PHOTO_AND_ONE_SHOT
    # Нажата ровно одна миниатюра, и это тот кадр, что стоит в главном окне
    assert len(pressed) == 1
    assert "halo.jpg" in pressed[0]


def test_filters_drawer_opener_announces_its_state(
    client: Client, shop: SimpleNamespace
) -> None:
    """Кнопка мобильного drawer — раскрывающая, её состояние объявляется."""
    html = page_html(client, "/catalog/zerkala/")

    opener = next(tag for tag in buttons(html) if "data-drawer-open" in tag)

    assert 'aria-expanded="false"' in opener
    assert 'aria-controls="filters-drawer"' in opener
    assert 'id="filters-drawer"' in html


def test_draft_product_404(client: Client, shop: SimpleNamespace) -> None:
    response = client.get("/catalog/zerkala/draft/")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_product_under_wrong_category_404(
    client: Client, shop: SimpleNamespace
) -> None:
    other = Category.objects.create(name="Перегородки", slug="peregorodki")
    Product.objects.create(
        category=other,
        name="Перегородка",
        slug="p",
        price=30000,
        is_published=True,
    )

    response = client.get("/catalog/peregorodki/halo-moon/")

    assert response.status_code == HTTPStatus.NOT_FOUND
