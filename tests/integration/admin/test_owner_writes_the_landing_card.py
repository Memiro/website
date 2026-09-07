"""The owner writes the landing card, and every write goes through an interactor (ADR-0012)."""

from http import HTTPStatus
from typing import Any, cast

import pytest
from django.apps import apps
from django.db.models import Manager
from django.test import AsyncClient

from memiro.application.errors.catalog import AttributeValueInUseError
from memiro.entities.common.identifiers import LandingId
from memiro.entities.errors.landing import InvalidLandingNarrowingError
from memiro.presentation.django_admin.refusals import REFUSAL_MESSAGES
from tests.common.factory.catalog import CONTOUR, RECTANGULAR, ROUND, SILVER
from tests.integration.admin.arrange import arranged_landing, landing_post

pytestmark = pytest.mark.usefixtures("admin_site", "primed_catalog")

APP = "memiro"
CHANGELIST_URL = f"/admin/{APP}/landing/"
ADD_URL = f"{CHANGELIST_URL}add/"


def _landings() -> Manager[Any]:
    """Reach the landing mirror; the app registry is only ready once Django is configured."""
    return cast("Manager[Any]", apps.get_model(APP, "Landing").objects)


def _card_url(landing_id: LandingId) -> str:
    return f"{CHANGELIST_URL}{landing_id}/change/"


async def test_the_owner_enters_a_landing_from_its_card(owner_client: AsyncClient) -> None:
    """The card is posted once and the page exists with the narrowing the owner ticked."""
    response = await owner_client.post(ADD_URL, landing_post(heading="Круглые зеркала", slug="kruglye-zerkala"))

    assert response.status_code == HTTPStatus.FOUND
    stored = await _landings().aget(slug="kruglye-zerkala")
    assert stored.heading == "Круглые зеркала"
    narrowing = [condition.value_id async for condition in stored.conditions.all()]
    assert narrowing == [ROUND]


async def test_the_card_of_a_saved_page_replaces_its_narrowing(owner_client: AsyncClient) -> None:
    """The set of conditions is one command of the aggregate, not a row edited at a time."""
    landing_id = arranged_landing(heading="Круглые зеркала", slug="kruglye-zerkala-2")

    response = await owner_client.post(
        _card_url(landing_id),
        landing_post(heading="Круглые зеркала", slug="kruglye-zerkala-2", narrowing=[CONTOUR], stored_conditions=1),
    )

    assert response.status_code == HTTPStatus.FOUND
    stored = await _landings().aget(pk=landing_id)
    narrowing = [condition.value_id async for condition in stored.conditions.all()]
    assert narrowing == [CONTOUR]


async def test_a_value_the_sidebar_does_not_offer_is_not_on_the_card(owner_client: AsyncClient) -> None:
    """The narrowing offers exactly what the sidebar builds: the card refuses the rest before the domain does."""
    response = await owner_client.post(
        ADD_URL,
        landing_post(heading="Серебряные зеркала", slug="serebryanye-zerkala", narrowing=[SILVER]),
    )

    assert response.status_code == HTTPStatus.OK
    assert not await _landings().filter(slug="serebryanye-zerkala").aexists()


async def test_the_whole_dictionary_of_an_attribute_is_refused(owner_client: AsyncClient) -> None:
    """Every value ticked is the category itself under a second address."""
    response = await owner_client.post(
        ADD_URL,
        landing_post(heading="Любые зеркала", slug="lyubye-zerkala", narrowing=[ROUND, RECTANGULAR]),
        follow=True,
    )

    assert REFUSAL_MESSAGES[InvalidLandingNarrowingError] in response.content.decode()
    assert not await _landings().filter(slug="lyubye-zerkala").aexists()


async def test_the_owner_takes_a_page_off_the_storefront_from_its_card(owner_client: AsyncClient) -> None:
    """Deletion goes through the interactor, and the narrowing goes with the page."""
    landing_id = arranged_landing(heading="Фигурные зеркала", slug="figurnye-zerkala")

    response = await owner_client.post(f"{CHANGELIST_URL}{landing_id}/delete/", {"post": "yes"})

    assert response.status_code == HTTPStatus.FOUND
    assert not await _landings().filter(pk=landing_id).aexists()


async def test_a_value_a_landing_narrows_by_cannot_leave_the_dictionary(owner_client: AsyncClient) -> None:
    """ATTRIBUTE_VALUE_IN_USE: the page would stop being the page its address promises."""
    arranged_landing(heading="Круглые зеркала", slug="kruglye-zerkala-3")
    shape = await apps.get_model(APP, "AttributeValue").objects.aget(pk=ROUND)

    response = await owner_client.post(
        f"/admin/{APP}/attribute/{shape.attribute_id}/delete/",
        {"post": "yes"},
        follow=True,
    )

    shown = response.content.decode()
    assert REFUSAL_MESSAGES[AttributeValueInUseError] in shown or "Посадочные" in shown
