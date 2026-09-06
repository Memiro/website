"""The owner writes the attribute card, and every write goes through an interactor (ADR-0012).

The card is the only screen whose refusal to write is lifted in this slice:
the rest of the mirrors stay read-only until their own tickets.
"""

from http import HTTPStatus
from typing import Any, cast
from uuid import uuid4

import pytest
from django.apps import apps
from django.db.models import Manager, QuerySet
from django.test import AsyncClient

from memiro.application.common.input_limits import MAX_ATTRIBUTE_PARENTS, MAX_ATTRIBUTE_VALUES
from memiro.application.errors.catalog import AttributeInUseError, AttributeValueInUseError
from memiro.entities.common.identifiers import AttributeId
from memiro.presentation.django_admin.refusals import REFUSAL_MESSAGES
from memiro.presentation.django_admin.writes import PARTLY_SAVED
from tests.common.factory.catalog import BACKLIGHT, CONTOUR, NO_BACKLIGHT, PRODUCT
from tests.integration.admin.arrange import arranged_attribute, card_post, row, value_form

pytestmark = pytest.mark.usefixtures("admin_site", "primed_catalog")

APP = "memiro"
# Django's own flag for "this row was added", spelled where the constant
# cannot be imported before the app registry is ready.
ADDITION = 1
CHANGE = 2
LOGIN_URL = "/admin/login/"
CHANGELIST_URL = f"/admin/{APP}/attribute/"
ADD_URL = f"{CHANGELIST_URL}add/"
# Every mirror the admin registers, written out rather than filtered out of the
# registry: the expected value of a test is spelled, not computed (§14.1/003).
ADD_URLS = (
    ADD_URL,
    f"/admin/{APP}/category/add/",
    f"/admin/{APP}/attributevalue/add/",
    f"/admin/{APP}/product/add/",
    f"/admin/{APP}/productvariant/add/",
    f"/admin/{APP}/pricingsettings/add/",
    f"/admin/{APP}/inquiry/add/",
    f"/admin/{APP}/inquiryitem/add/",
)
# What the demo backlight holds before a card touches it (the contour tape and
# the row that says there is no backlight at all) and what its root is called.
BACKLIGHT_ROWS = [CONTOUR, NO_BACKLIGHT]
BACKLIGHT_NAME = "Подсветка"


def _attributes() -> Manager[Any]:
    """Reach the attribute mirror; the app registry is only ready once Django is configured."""
    return cast("Manager[Any]", apps.get_model(APP, "Attribute").objects)


def _values_of(attribute_id: AttributeId) -> QuerySet[Any]:
    """Reach the dictionary of one attribute in the order the owner gave it."""
    values = apps.get_model(APP, "AttributeValue").objects.filter(attribute_id=attribute_id)
    return cast("QuerySet[Any]", values.order_by("sort_order"))


def _card_url(attribute_id: AttributeId) -> str:
    return f"{CHANGELIST_URL}{attribute_id}/change/"


def _delete_url(attribute_id: AttributeId) -> str:
    return f"{CHANGELIST_URL}{attribute_id}/delete/"


async def _names_of(attribute_id: AttributeId) -> list[str]:
    """Read the dictionary of one attribute back in the order the owner gave it."""
    return [value.name async for value in _values_of(attribute_id)]


async def _identifiers_of(attribute_id: AttributeId) -> list[AttributeId]:
    """Read the identifiers of one dictionary back in the order the owner gave it."""
    return [value.id async for value in _values_of(attribute_id)]


async def test_the_owner_creates_an_attribute_with_its_dictionary_from_one_card(owner_client: AsyncClient) -> None:
    """The card of a new attribute reaches the domain as one command, its rows included."""
    response = await owner_client.post(
        ADD_URL,
        card_post(name="Фацет", rows=[row(name="Есть"), row(name="Нет", amount="0", sort_order=2)]),
    )

    assert response.status_code == HTTPStatus.FOUND
    created = await _attributes().aget(name="Фацет")
    assert await _names_of(created.id) == ["Есть", "Нет"]


async def test_the_owner_restates_the_root_and_the_dictionary_of_a_saved_attribute(
    owner_client: AsyncClient,
) -> None:
    """One save of the card carries both halves: the renamed root and the replaced set of rows."""
    attribute_id = arranged_attribute(name="Кромка", values=[value_form(name="Полированная")])
    kept = (await _identifiers_of(attribute_id))[0]

    response = await owner_client.post(
        _card_url(attribute_id),
        card_post(
            name="Обработка кромки",
            rows=[row(name="Полированная", value_id=kept), row(name="Еврокромка", sort_order=2)],
            kept_rows=1,
        ),
    )

    assert response.status_code == HTTPStatus.FOUND
    assert (await _attributes().aget(id=attribute_id)).name == "Обработка кромки"
    assert await _names_of(attribute_id) == ["Полированная", "Еврокромка"]


async def test_the_card_the_owner_saved_is_written_to_the_history(owner_client: AsyncClient) -> None:
    """The Django half of the write records the addition the owner made."""
    await owner_client.post(ADD_URL, card_post(name="Пескоструй", rows=[row(name="Рисунок")]))

    created = await _attributes().aget(name="Пескоструй")
    history = cast("Manager[Any]", apps.get_model("admin", "LogEntry").objects)
    assert await history.filter(object_id=str(created.id), action_flag=ADDITION).aexists()


async def test_the_history_records_the_card_the_owner_restated(owner_client: AsyncClient) -> None:
    """The Django half records the change as well: the owner reads his own edits back."""
    attribute_id = arranged_attribute(name="Подвес", values=[value_form(name="Тросик")])
    kept = (await _identifiers_of(attribute_id))[0]

    await owner_client.post(
        _card_url(attribute_id),
        card_post(name="Подвес зеркала", rows=[row(name="Тросик", value_id=kept)], kept_rows=1),
    )

    history = cast("Manager[Any]", apps.get_model("admin", "LogEntry").objects)
    assert await history.filter(object_id=str(attribute_id), action_flag=CHANGE).aexists()


async def test_the_owner_removes_an_attribute_nothing_depends_on(owner_client: AsyncClient) -> None:
    """Deletion from the card goes through the interactor that guards what still uses the attribute."""
    attribute_id = arranged_attribute(name="Упаковка", values=[value_form(name="Коробка")])

    response = await owner_client.post(_delete_url(attribute_id), {"post": "yes"})

    assert response.status_code == HTTPStatus.FOUND
    assert not await _attributes().filter(id=attribute_id).aexists()


async def test_a_card_dropping_a_declared_row_comes_back_with_a_message_and_changes_nothing(
    owner_client: AsyncClient,
) -> None:
    """ATTRIBUTE_VALUE_IN_USE: the mirror declares "no backlight", so neither rows nor root move."""
    response = await owner_client.post(
        _card_url(BACKLIGHT),
        card_post(name="Подсветка навсегда", rows=[row(name="Контурная", value_id=CONTOUR)], kept_rows=2),
        follow=True,
    )

    shown = response.content.decode()
    assert REFUSAL_MESSAGES[AttributeValueInUseError] in shown
    assert "Зеркало в раме" in shown
    assert await _identifiers_of(BACKLIGHT) == BACKLIGHT_ROWS
    assert (await _attributes().aget(id=BACKLIGHT)).name == BACKLIGHT_NAME


async def test_a_card_refused_on_its_root_says_that_the_dictionary_already_landed(
    owner_client: AsyncClient,
) -> None:
    """INVALID_ATTRIBUTE_PARENT: the root is a second command, and the owner is told what did land."""
    attribute_id = arranged_attribute(name="Крепление", values=[value_form(name="Скрытое")])
    kept = (await _identifiers_of(attribute_id))[0]

    response = await owner_client.post(
        _card_url(attribute_id),
        card_post(
            name="Крепление зеркала",
            rows=[row(name="Скрытое", value_id=kept), row(name="Открытое", sort_order=2)],
            parents=[attribute_id],
            kept_rows=1,
        ),
        follow=True,
    )

    assert PARTLY_SAVED in response.content.decode()
    assert await _names_of(attribute_id) == ["Скрытое", "Открытое"]
    assert (await _attributes().aget(id=attribute_id)).name == "Крепление"


async def test_removing_an_attribute_something_still_holds_comes_back_with_a_message(
    owner_client: AsyncClient,
) -> None:
    """ATTRIBUTE_IN_USE: heating depends on backlight and the mirror declares it, so backlight stays."""
    response = await owner_client.post(_delete_url(BACKLIGHT), {"post": "yes"}, follow=True)

    shown = response.content.decode()
    assert REFUSAL_MESSAGES[AttributeInUseError] in shown
    assert "Подогрев" in shown
    assert await _attributes().filter(id=BACKLIGHT).aexists()


async def test_a_card_with_one_row_over_the_limit_is_refused_by_the_form(owner_client: AsyncClient) -> None:
    """The card refuses more rows than the production constant allows, and stores nothing."""
    response = await owner_client.post(
        ADD_URL,
        card_post(
            name="Слишком длинный справочник",
            rows=[row(name=f"Значение {number}", sort_order=number) for number in range(MAX_ATTRIBUTE_VALUES + 1)],
        ),
    )

    assert response.status_code == HTTPStatus.OK
    assert not await _attributes().filter(name="Слишком длинный справочник").aexists()


async def test_only_the_attribute_card_offers_the_owner_a_form(owner_client: AsyncClient) -> None:
    """The refusal to write is lifted from the attribute screens alone (ticket 09)."""
    statuses = {url: (await owner_client.get(url)).status_code for url in ADD_URLS}

    assert statuses == {
        ADD_URL: HTTPStatus.OK,
        f"/admin/{APP}/category/add/": HTTPStatus.FORBIDDEN,
        f"/admin/{APP}/attributevalue/add/": HTTPStatus.FORBIDDEN,
        f"/admin/{APP}/product/add/": HTTPStatus.FORBIDDEN,
        f"/admin/{APP}/productvariant/add/": HTTPStatus.FORBIDDEN,
        f"/admin/{APP}/pricingsettings/add/": HTTPStatus.FORBIDDEN,
        f"/admin/{APP}/inquiry/add/": HTTPStatus.FORBIDDEN,
        f"/admin/{APP}/inquiryitem/add/": HTTPStatus.FORBIDDEN,
    }


async def test_another_mirror_refuses_the_card_the_owner_posts_to_it(owner_client: AsyncClient) -> None:
    """A write aimed at a read-only mirror is refused by the screen, not by the domain."""
    response = await owner_client.post(f"/admin/{APP}/product/{PRODUCT}/change/", {"name": "Переименован"})

    assert response.status_code == HTTPStatus.FORBIDDEN


async def test_a_stranger_writes_nothing_from_the_card() -> None:
    """An unauthenticated POST is sent to the login page and leaves the dictionary alone."""
    stranger = AsyncClient()

    response = await stranger.post(ADD_URL, card_post(name="Незваный", rows=[row(name="Строка")]))

    assert response.headers["Location"].startswith(LOGIN_URL)
    assert not await _attributes().filter(name="Незваный").aexists()


async def test_a_card_of_an_attribute_nobody_issued_is_not_found(owner_client: AsyncClient) -> None:
    """An identifier nobody issued names no card: the screen answers before the domain does."""
    response = await owner_client.post(
        _card_url(uuid4()),
        card_post(name="Ничей", rows=[row(name="Строка")]),
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.headers["Location"] == "/admin/"


async def test_a_card_with_one_dependency_over_the_limit_is_refused_by_the_form(
    owner_client: AsyncClient,
) -> None:
    """The card refuses more dependencies than the production constant allows, and stores nothing."""
    parents = [
        arranged_attribute(name=f"Зависимость {number}", values=[value_form(name="Строка")])
        for number in range(MAX_ATTRIBUTE_PARENTS + 1)
    ]

    response = await owner_client.post(
        ADD_URL,
        card_post(name="Слишком зависимый", rows=[row(name="Строка")], parents=parents),
    )

    assert response.status_code == HTTPStatus.OK
    assert not await _attributes().filter(name="Слишком зависимый").aexists()
