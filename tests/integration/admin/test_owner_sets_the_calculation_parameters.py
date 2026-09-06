"""«Параметры расчёта»: the owner moves the bounds the price is calculated within (ADR-0010).

The site has one row of settings, so the changelist is not a screen — it sends
the owner to the object. Bounds and the surcharge table are one aggregate and
travel as one command: a refused tier leaves every bound where it was.
"""

from decimal import Decimal
from http import HTTPStatus
from typing import Any, cast

import pytest
from django.apps import apps
from django.db.models import Manager
from django.test import AsyncClient

from memiro.entities.errors.pricing import DuplicateSizeSurchargeError, InvalidSurchargeFactorError
from memiro.entities.pricing.pricing_settings import PRICING_SETTINGS_ID
from memiro.presentation.django_admin.refusals import REFUSAL_MESSAGES
from tests.integration.admin.arrange import (
    PricingBounds,
    arranged_pricing_settings,
    pricing_post,
    rendered_form,
    tier,
)

pytestmark = pytest.mark.usefixtures("admin_site", "primed_catalog")

APP = "memiro"
CHANGELIST_URL = f"/admin/{APP}/pricingsettings/"
CARD_URL = f"{CHANGELIST_URL}{PRICING_SETTINGS_ID}/change/"
# Django's own flag for "this row was changed", spelled where the constant
# cannot be imported before the app registry is ready.
CHANGE = 2
# The bounds the owner leaves the site at, and the ones a test arranges before
# posting something the domain refuses.
NEW_BOUNDS = PricingBounds(min_area="0.35", min_order_total="3000", max_long_side_mm=3200, max_short_side_mm=2500)
KNOWN_BOUNDS = PricingBounds(min_area="0.25", min_order_total="2000", max_long_side_mm=2000, max_short_side_mm=1500)


def _settings() -> Manager[Any]:
    """Reach the settings mirror; the app registry is only ready once Django is configured."""
    return cast("Manager[Any]", apps.get_model(APP, "PricingSettings").objects)


def _tiers() -> Manager[Any]:
    """Reach the surcharge mirror the same way."""
    return cast("Manager[Any]", apps.get_model(APP, "SizeSurcharge").objects)


async def _stored_tiers() -> list[tuple[int, Decimal]]:
    """Read the surcharge table back, lowest threshold first."""
    return [
        (row.from_long_side_mm, row.factor)
        async for row in _tiers().all().order_by("from_long_side_mm")  # pyright: ignore[reportUnknownMemberType]
    ]


async def _stored_long_side() -> int:
    """Read the production limit on the longest side back."""
    return cast("int", (await _settings().aget(id=PRICING_SETTINGS_ID)).max_long_side_mm)


def _history() -> Manager[Any]:
    """Reach Django's own history; the app registry is only ready once Django is configured."""
    return cast("Manager[Any]", apps.get_model("admin", "LogEntry").objects)


async def test_the_owner_restates_the_bounds_of_calculation(owner_client: AsyncClient) -> None:
    """Every bound typed on the screen reaches the domain through the one command of the aggregate."""
    response = await owner_client.post(
        CARD_URL,
        pricing_post(bounds=NEW_BOUNDS, tiers=[tier(from_long_side_mm=2200, factor="1.25")]),
    )

    assert response.status_code == HTTPStatus.FOUND
    stored = await _settings().aget(id=PRICING_SETTINGS_ID)
    assert (stored.min_area, stored.min_order_total) == (Decimal("0.35"), Decimal(3000))
    assert (stored.max_long_side_mm, stored.max_short_side_mm) == (3200, 2500)


async def test_the_owner_replaces_the_whole_surcharge_table(owner_client: AsyncClient) -> None:
    """The table is replaced, not merged: the tier the owner did not submit is gone."""
    arranged_pricing_settings(KNOWN_BOUNDS, tiers=[(1800, "1.1")])

    await owner_client.post(
        CARD_URL,
        pricing_post(
            bounds=KNOWN_BOUNDS,
            tiers=[tier(from_long_side_mm=2200, factor="1.25"), tier(from_long_side_mm=2600, factor="1.5")],
        ),
    )

    assert await _stored_tiers() == [(2200, Decimal("1.25")), (2600, Decimal("1.5"))]


async def test_the_owner_reprices_a_tier_by_posting_back_the_card_he_was_shown(
    owner_client: AsyncClient,
) -> None:
    """A tier carries no identity to post back: the browser's own round trip must reach the domain."""
    arranged_pricing_settings(KNOWN_BOUNDS, tiers=[(1800, "1.1")])
    posted = rendered_form((await owner_client.get(CARD_URL)).content.decode())

    response = await owner_client.post(CARD_URL, posted | {"size_surcharges-0-factor": "1.4"})

    assert response.status_code == HTTPStatus.FOUND
    assert await _stored_tiers() == [(1800, Decimal("1.4"))]


async def test_the_changelist_sends_the_owner_to_the_only_object_there_is(owner_client: AsyncClient) -> None:
    """A list of one row is not a screen: the changelist redirects to the settings themselves."""
    response = await owner_client.get(CHANGELIST_URL)

    assert response.status_code == HTTPStatus.FOUND
    assert response.headers["Location"] == CARD_URL


async def test_the_screen_names_the_order_the_production_limit_is_raised_in(owner_client: AsyncClient) -> None:
    """ADR-0010: the surcharge tiers are entered before the limit goes up, and the screen says so."""
    shown = (await owner_client.get(CARD_URL)).content.decode()

    assert "как заведены ступени наценки" in shown


async def test_the_screen_the_owner_saved_is_written_to_the_history(owner_client: AsyncClient) -> None:
    """The Django half of the write records the change the owner made."""
    await owner_client.post(CARD_URL, pricing_post(bounds=NEW_BOUNDS, tiers=[]))

    assert await _history().filter(object_id=str(PRICING_SETTINGS_ID), action_flag=CHANGE).aexists()


async def test_the_settings_can_be_neither_added_nor_deleted(owner_client: AsyncClient) -> None:
    """The row is born with the site: without it the catalogue has no price at all."""
    statuses = (
        (await owner_client.get(f"{CHANGELIST_URL}add/")).status_code,
        (await owner_client.get(f"{CARD_URL[: -len('change/')]}delete/")).status_code,
    )

    assert statuses == (HTTPStatus.FORBIDDEN, HTTPStatus.FORBIDDEN)


async def test_a_tier_that_would_not_raise_the_price_is_refused_and_nothing_is_saved(
    owner_client: AsyncClient,
) -> None:
    """INVALID_SURCHARGE_FACTOR: a factor of one is refused, and the bounds keep their old values."""
    arranged_pricing_settings(KNOWN_BOUNDS, tiers=[(1800, "1.1")])

    response = await owner_client.post(
        CARD_URL,
        pricing_post(bounds=NEW_BOUNDS, tiers=[tier(from_long_side_mm=2200, factor="1")]),
        follow=True,
    )

    assert REFUSAL_MESSAGES[InvalidSurchargeFactorError] in response.content.decode()
    assert await _stored_long_side() == KNOWN_BOUNDS.max_long_side_mm
    assert await _stored_tiers() == [(1800, Decimal("1.1"))]


async def test_two_tiers_starting_at_one_threshold_are_refused_and_nothing_is_saved(
    owner_client: AsyncClient,
) -> None:
    """DUPLICATE_SIZE_SURCHARGE: an ambiguous table is refused, and the bounds keep their old values."""
    arranged_pricing_settings(KNOWN_BOUNDS, tiers=[(1800, "1.1")])

    response = await owner_client.post(
        CARD_URL,
        pricing_post(
            bounds=NEW_BOUNDS,
            tiers=[tier(from_long_side_mm=2200, factor="1.25"), tier(from_long_side_mm=2200, factor="1.5")],
        ),
        follow=True,
    )

    assert REFUSAL_MESSAGES[DuplicateSizeSurchargeError] in response.content.decode()
    assert await _stored_long_side() == KNOWN_BOUNDS.max_long_side_mm
    assert await _stored_tiers() == [(1800, Decimal("1.1"))]
