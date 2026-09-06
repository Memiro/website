"""«Материалы и цены»: the owner prices the dictionary of every attribute from one flat list.

The screen edits the price half of a row and nothing else — naming, ordering,
"means absence", adding and removing a row stay on the card of the attribute
(decision 4). The command is the card's own ``replace_values``, so no second
truth about the price is entered into the system.
"""

from decimal import Decimal
from http import HTTPStatus
from typing import Any, cast

import pytest
from django.apps import apps
from django.db.models import Manager
from django.test import AsyncClient

from memiro.entities.catalog.attribute.rate import Unit
from memiro.entities.common.identifiers import AttributeId, AttributeValueId
from memiro.entities.errors.attribute import InvalidFactorRateError
from memiro.presentation.django_admin.refusals import REFUSAL_MESSAGES
from memiro.presentation.django_admin.writes import PARTLY_SAVED
from tests.common.factory.catalog import BACKLIGHT, CONTOUR, NO_BACKLIGHT
from tests.integration.admin.arrange import priced_list_post, priced_row

pytestmark = pytest.mark.usefixtures("admin_site", "primed_catalog")

APP = "memiro"
CHANGELIST_URL = f"/admin/{APP}/attributevalue/"
CARD_URL = f"/admin/{APP}/attribute/{BACKLIGHT}/change/"


def _values() -> Manager[Any]:
    """Reach the dictionary mirror; the app registry is only ready once Django is configured."""
    return cast("Manager[Any]", apps.get_model(APP, "AttributeValue").objects)


async def _amount_of(value_id: AttributeValueId) -> Decimal:
    """Read the tariff of one dictionary row back."""
    return cast("Decimal", (await _values().aget(id=value_id)).rate_amount)


async def _unit_of(value_id: AttributeValueId) -> str:
    """Read the unit of consumption of one dictionary row back."""
    return cast("str", (await _values().aget(id=value_id)).rate_unit)


async def _names_of(attribute_id: AttributeId) -> list[str]:
    """Read the dictionary of one attribute back in the order the owner gave it."""
    return [value.name async for value in _values().filter(attribute_id=attribute_id).order_by("sort_order")]


async def test_the_owner_prices_one_row_of_the_flat_list(owner_client: AsyncClient) -> None:
    """A tariff typed into the row reaches the domain through the command of its attribute."""
    response = await owner_client.post(
        CHANGELIST_URL,
        priced_list_post([priced_row(value_id=CONTOUR, amount="3100", unit=Unit.LINEAR_METER)]),
    )

    assert response.status_code == HTTPStatus.FOUND
    assert await _amount_of(CONTOUR) == Decimal(3100)


async def test_the_owner_moves_a_row_to_another_unit_of_consumption(owner_client: AsyncClient) -> None:
    """The unit is the fourth column the screen edits: a row leaves the metre it was priced in."""
    response = await owner_client.post(
        CHANGELIST_URL,
        priced_list_post([priced_row(value_id=CONTOUR, amount="3100", unit=Unit.SQUARE_METER)]),
    )

    assert response.status_code == HTTPStatus.FOUND
    assert await _unit_of(CONTOUR) == Unit.SQUARE_METER.name


async def test_the_card_of_the_attribute_shows_the_price_the_flat_list_saved(owner_client: AsyncClient) -> None:
    """One dictionary, one price: what the flat list stored is what the card reads back."""
    await owner_client.post(
        CHANGELIST_URL,
        priced_list_post([priced_row(value_id=CONTOUR, amount="3200", unit=Unit.LINEAR_METER)]),
    )

    shown = (await owner_client.get(CARD_URL)).content.decode()

    assert "3200" in shown


async def test_pricing_one_row_leaves_the_rest_of_its_dictionary_alone(owner_client: AsyncClient) -> None:
    """The row travels back inside its dictionary, and the neighbours it travels with do not move."""
    before = await _names_of(BACKLIGHT)

    await owner_client.post(
        CHANGELIST_URL,
        priced_list_post([priced_row(value_id=CONTOUR, amount="3300", unit=Unit.LINEAR_METER)]),
    )

    assert await _names_of(BACKLIGHT) == before
    assert await _amount_of(NO_BACKLIGHT) == 0


async def test_the_owner_moves_both_scaling_marks_from_the_flat_list(owner_client: AsyncClient) -> None:
    """Both "multiplied by" marks are the owner's to set from the same row."""
    await owner_client.post(
        CHANGELIST_URL,
        priced_list_post(
            [
                priced_row(
                    value_id=CONTOUR,
                    amount="3400",
                    unit=Unit.LINEAR_METER,
                    scaled_by_shape=True,
                    scaled_by_size_surcharge=True,
                )
            ]
        ),
    )

    priced = await _values().aget(id=CONTOUR)
    assert priced.scaled_by_shape
    assert priced.scaled_by_size_surcharge


async def test_the_flat_list_does_not_rename_a_row(owner_client: AsyncClient) -> None:
    """A name posted alongside the price is not a column of this screen and is ignored."""
    await owner_client.post(
        CHANGELIST_URL,
        priced_list_post(
            [priced_row(value_id=CONTOUR, amount="3500", unit=Unit.LINEAR_METER, extra={"name": "Переименованная"})]
        ),
    )

    assert (await _values().aget(id=CONTOUR)).name == "Контурная"


async def test_the_flat_list_offers_neither_a_new_row_nor_a_deletion(owner_client: AsyncClient) -> None:
    """Adding and removing a dictionary row belong to the card of the attribute, not here."""
    statuses = (
        (await owner_client.get(f"{CHANGELIST_URL}add/")).status_code,
        (await owner_client.get(f"{CHANGELIST_URL}{CONTOUR}/delete/")).status_code,
    )

    assert statuses == (HTTPStatus.FORBIDDEN, HTTPStatus.FORBIDDEN)


async def test_a_row_priced_below_what_a_factor_allows_comes_back_with_a_message(
    owner_client: AsyncClient,
) -> None:
    """INVALID_FACTOR_RATE: a multiplier of zero is refused, and the row keeps the price it had."""
    response = await owner_client.post(
        CHANGELIST_URL,
        priced_list_post([priced_row(value_id=CONTOUR, amount="0", unit=Unit.FACTOR)]),
        follow=True,
    )

    assert REFUSAL_MESSAGES[InvalidFactorRateError] in response.content.decode()
    assert await _amount_of(CONTOUR) != 0


async def test_a_refusal_on_the_second_row_owns_up_to_the_first_one_landing(owner_client: AsyncClient) -> None:
    """A page of edits is a command per row: the banner says so instead of promising nothing changed."""
    response = await owner_client.post(
        CHANGELIST_URL,
        priced_list_post(
            [
                priced_row(value_id=CONTOUR, amount="3600", unit=Unit.LINEAR_METER),
                priced_row(value_id=NO_BACKLIGHT, amount="0", unit=Unit.FACTOR),
            ]
        ),
        follow=True,
    )

    assert PARTLY_SAVED in response.content.decode()
    assert await _amount_of(CONTOUR) == Decimal(3600)
