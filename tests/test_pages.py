from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from memiro.content.models import Work


def test_about_page(client: Client, db: None) -> None:
    response = client.get("/about/")
    content = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert "О нас" in content
    assert "производство" in content


def test_delivery_page_contains_no_return_clause(
    client: Client, db: None
) -> None:
    """Оговорка ст. 26.1 ЗоЗПП — главный защитный текст студии."""
    response = client.get("/delivery/")
    content = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert "Доставка и возврат" in content
    assert "ст. 26.1" in content
    assert "возврату" in content
    assert "не подлежат" in content


def test_contacts_page_has_address_hours_and_map(
    client: Client, db: None
) -> None:
    response = client.get("/contacts/")
    content = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert "Александра Матросова, 4к2ж" in content
    assert "по предварительной записи" in content
    assert "yandex.ru/map-widget" in content


def test_contacts_map_is_not_loaded_before_click(
    client: Client, db: None
) -> None:
    """Виджет Яндекса ставит куки — до нажатия iframe в разметке нет."""
    content = client.get("/contacts/").content.decode()

    assert "<iframe" not in content
    assert "data-map-load" in content


def test_nav_links_static_pages(client: Client, db: None) -> None:
    """Шапка и футер ведут на реальные страницы, а не на #."""
    content = client.get("/").content.decode()

    for url in ("/about/", "/delivery/", "/contacts/", "/works/"):
        assert f'href="{url}"' in content


@pytest.mark.django_db
def test_works_gallery_shows_only_published(client: Client) -> None:
    Work.objects.create(
        title="Зеркало в спальне",
        image="works/bedroom.jpg",
        is_published=True,
    )
    Work.objects.create(
        title="Скрытая работа",
        image="works/hidden.jpg",
    )

    response = client.get("/works/")
    content = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert "Наши работы" in content
    assert "Зеркало в спальне" in content
    assert "Скрытая работа" not in content


@pytest.mark.django_db
def test_works_ordered_manually(client: Client) -> None:
    Work.objects.create(
        title="Вторая", image="works/2.jpg", is_published=True, order=2
    )
    Work.objects.create(
        title="Первая", image="works/1.jpg", is_published=True, order=1
    )

    content = client.get("/works/").content.decode()

    assert content.index("Первая") < content.index("Вторая")


@pytest.mark.django_db
def test_works_admin_registered(client: Client) -> None:
    get_user_model().objects.create_superuser(
        username="owner",
        email="owner@example.com",
        password="owner-password",
    )
    client.login(username="owner", password="owner-password")

    response = client.get("/admin/content/work/")

    assert response.status_code == HTTPStatus.OK
