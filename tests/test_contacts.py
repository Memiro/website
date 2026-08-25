"""Контакты студии живут в админке, а не в коде (тикет 01)."""

from datetime import time
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from memiro.content.models import SiteContacts


@pytest.mark.django_db
def test_migration_carried_contacts_from_code() -> None:
    """Первая строка заведена миграцией: витрина не пустеет на выкатке."""
    contacts = SiteContacts.load()

    assert contacts.pk == SiteContacts.SINGLETON_PK
    assert contacts.city == "Санкт-Петербург"
    assert contacts.street == "Александра Матросова, 4к2ж"
    assert contacts.phone
    assert contacts.email


@pytest.mark.django_db
def test_address_joins_city_and_street() -> None:
    """Разметке город и улица нужны порознь, витрине — одной строкой."""
    assert SiteContacts(city="Псков", street="Рижский, 5").address == (
        "Псков, Рижский, 5"
    )


@pytest.mark.django_db
def test_second_row_overwrites_the_first() -> None:
    """Вторые контакты — вторая правда: строка на сайте одна."""
    SiteContacts(city="Псков", street="Рижский, 5").save()

    assert SiteContacts.objects.count() == 1
    assert SiteContacts.load().city == "Псков"


@pytest.mark.django_db
def test_half_a_schedule_is_rejected() -> None:
    """Одна граница расписания молча пропала бы — админка не даёт."""
    contacts = SiteContacts.load()
    contacts.opens = time(10, 0)

    with pytest.raises(ValidationError):
        contacts.full_clean()


@pytest.mark.django_db
def test_contacts_page_prints_values_from_admin(client: Client) -> None:
    contacts = SiteContacts.load()
    contacts.city = "Псков"
    contacts.street = "Рижский проспект, 5"
    contacts.phone_display = "+7 811 111-11-11"
    contacts.hours = "Будни с утра"
    contacts.save()

    content = client.get("/contacts/").content.decode()

    assert "Псков, Рижский проспект, 5" in content
    assert "+7 811 111-11-11" in content
    assert "Будни с утра" in content


@pytest.mark.django_db
def test_footer_prints_values_from_admin(client: Client) -> None:
    """Футер есть на каждой странице — контакты там те же."""
    contacts = SiteContacts.load()
    contacts.email = "owner@example.com"
    contacts.save()

    content = client.get("/about/").content.decode()

    assert "owner@example.com" in content


@pytest.mark.django_db
def test_empty_link_gives_no_icon(client: Client) -> None:
    """Пустая ссылка значит «не показывать», а не иконку в никуда."""
    contacts = SiteContacts.load()
    contacts.max_link = ""
    contacts.vk = ""
    contacts.map_embed = ""
    contacts.save()

    content = client.get("/contacts/").content.decode()

    assert 'href=""' not in content
    assert "MAX" not in content
    assert "data-map-src" not in content


@pytest.mark.django_db
@pytest.mark.parametrize("page", ["/", "/contacts/", "/about/"])
def test_storefront_messengers_are_max_only(client: Client, page: str) -> None:
    """Тикет 08: связь со студией — телефон, почта и MAX.

    Telegram и WhatsApp сняты с витрины целиком: шапка и футер
    приезжают на каждую страницу, «Контакты» и главная — свои блоки.
    """
    contacts = SiteContacts.load()
    contacts.max_link = "https://max.ru/memiro"
    contacts.save()

    content = client.get(page).content.decode()

    assert "Telegram" not in content
    assert "WhatsApp" not in content
    assert 'href="https://max.ru/memiro"' in content


@pytest.mark.django_db
def test_max_icon_stands_from_the_start_with_a_placeholder(
    client: Client,
) -> None:
    """Тикет 08: иконку владелец велел поставить до настоящей ссылки.

    Пустая ссылка обычно значит «не показывать», но заглушку сюда
    завела миграция: забыть про иконку легче, чем про пустое место.
    """
    assert SiteContacts.load().max_link

    content = client.get("/contacts/").content.decode()

    assert ">MAX</a>" in content


@pytest.mark.django_db
def test_max_link_comes_from_admin(client: Client) -> None:
    """Заглушку владелец меняет в админке, а не выкаткой."""
    contacts = SiteContacts.load()
    contacts.max_link = "https://max.ru/memiro"
    contacts.save()

    content = client.get("/contacts/").content.decode()

    assert 'href="https://max.ru/memiro"' in content


@pytest.mark.django_db
def test_contacts_admin_is_a_single_row(client: Client) -> None:
    """Контакты правят, а не заводят: ни «добавить», ни «удалить»."""
    get_user_model().objects.create_superuser(
        username="owner",
        email="owner@example.com",
        password="owner-password",
    )
    client.login(username="owner", password="owner-password")

    listing = client.get("/admin/content/sitecontacts/")
    form = client.get(
        f"/admin/content/sitecontacts/{SiteContacts.SINGLETON_PK}/change/"
    )

    assert listing.status_code == HTTPStatus.OK
    assert "/admin/content/sitecontacts/add/" not in listing.content.decode()
    assert form.status_code == HTTPStatus.OK
    assert "Александра Матросова" in form.content.decode()
    assert "_addanother" not in form.content.decode()


@pytest.mark.django_db
def test_contacts_are_read_once_per_request(client: Client) -> None:
    """Шаблон и разметка спрашивают одну строку — запрос к ней один."""
    with CaptureQueriesContext(connection) as captured:
        client.get("/contacts/")

    reads = [
        query
        for query in captured.captured_queries
        if "content_sitecontacts" in query["sql"]
    ]

    assert len(reads) == 1
