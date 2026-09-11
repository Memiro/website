"""The owner builds precalculated variants in the panel under the product card (ADR-0011).

The panel is not a form of the card: it writes through its own three JSON
answers, and every one of them is an interactor called across the bridge.
"""

import json
from collections.abc import Iterator
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from django.apps import apps
from django.db.models import Manager
from django.http import HttpResponse
from django.http.response import HttpResponseBase
from django.test import AsyncClient

from memiro.application.common.input_limits import MAX_SIDE_MM
from memiro.application.errors.catalog import ProductNotFoundError
from memiro.entities.common.identifiers import ProductId
from memiro.entities.errors.product import DuplicateVariantError, InvalidVariantConfigurationError
from memiro.presentation.django_admin import variant_builder
from memiro.presentation.django_admin.refusals import REFUSAL_MESSAGES
from tests.common.factory.catalog import BLADE, GRAPHITE, PRODUCT
from tests.integration.admin.arrange import arranged_product, arranged_variant, cleared_variants

pytestmark = pytest.mark.usefixtures("admin_site", "primed_catalog")


@pytest.fixture(autouse=True)
def _empty_panel() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]  # pytest calls it by its autouse registration
    """Leave the demo product without variants: the admin's database outlives one test."""
    yield
    cleared_variants()


APP = "memiro"
CHANGELIST_URL = f"/admin/{APP}/product/"
# The workbook price of the demo product at 800 × 600, as the owner reads it:
# the thousands and the sign stand apart on narrow no-break spaces.
WORKBOOK_PRICE = "8\u202f820\u202f₽"
PANEL_SCRIPT = Path(variant_builder.__file__).parent / "static" / "memiro" / "js" / "admin-variant-builder.js"
# What is left of a price label once its typography is taken away.
_ONLY_DIGITS = {ord(character): None for character in "\u202f₽ "}


def _products() -> Manager[Any]:
    """Reach the product mirror; the app registry is only ready once Django is configured."""
    return cast("Manager[Any]", apps.get_model(APP, "Product").objects)


def _variants() -> Manager[Any]:
    """Reach the variant mirror; the app registry is only ready once Django is configured."""
    return cast("Manager[Any]", apps.get_model(APP, "ProductVariant").objects)


def _card_url(product_id: ProductId) -> str:
    return f"{CHANGELIST_URL}{product_id}/change/"


def _price_url(product_id: ProductId) -> str:
    return f"{CHANGELIST_URL}{product_id}/variants/price/"


def _save_url(product_id: ProductId) -> str:
    return f"{CHANGELIST_URL}{product_id}/variants/save/"


def _delete_url(product_id: ProductId) -> str:
    return f"{CHANGELIST_URL}{product_id}/variants/delete/"


def _panel_post(*, width_mm: int = 800, height_mm: int = 600, sort_order: int = 0, **named: str) -> dict[str, str]:
    """Spell what the panel sends: its own field names, never the card's."""
    return {
        "width_mm": str(width_mm),
        "height_mm": str(height_mm),
        "sort_order": str(sort_order),
        **named,
    }


def _answer(response: HttpResponseBase) -> dict[str, Any]:
    """Read one JSON answer of the panel."""
    return cast("dict[str, Any]", json.loads(cast("HttpResponse", response).content))


async def test_the_owner_sees_the_price_of_a_variant_before_he_adds_it(owner_client: AsyncClient) -> None:
    """The panel quotes the assembled variant by the very function that would save it."""
    response = await owner_client.get(_price_url(PRODUCT), _panel_post())

    assert response.status_code == HTTPStatus.OK
    assert (_answer(response))["price_label"] == WORKBOOK_PRICE


async def test_the_price_the_panel_shows_is_the_price_the_added_variant_carries(
    owner_client: AsyncClient,
) -> None:
    """The quotation and the write answer one question with one number."""
    quoted = _answer(await owner_client.get(_price_url(PRODUCT), _panel_post()))

    saved = _answer(await owner_client.post(_save_url(PRODUCT), _panel_post()))

    assert [variant["price_label"] for variant in saved["variants"]] == [quoted["price_label"]]


async def test_the_owner_adds_a_variant_from_the_panel(owner_client: AsyncClient) -> None:
    """The panel writes the variant and answers with the whole redrawn list."""
    response = await owner_client.post(_save_url(PRODUCT), _panel_post(width_mm=900, height_mm=700, sort_order=3))

    assert response.status_code == HTTPStatus.OK
    answer = _answer(response)
    stored = await _variants().aget(id=answer["variants"][0]["variant_id"])
    assert (stored.product_id, stored.width_mm, stored.height_mm, stored.sort_order) == (PRODUCT, 900, 700, 3)


async def test_the_owner_changes_a_variant_from_the_panel(owner_client: AsyncClient) -> None:
    """A variant the panel names is rewritten, not doubled."""
    variant_id = arranged_variant(width_mm=800, height_mm=600)

    response = await owner_client.post(
        _save_url(PRODUCT),
        _panel_post(width_mm=1000, height_mm=800, variant=str(variant_id)),
    )

    assert response.status_code == HTTPStatus.OK
    assert len((_answer(response))["variants"]) == 1
    stored = await _variants().aget(id=variant_id)
    assert (stored.width_mm, stored.height_mm) == (1000, 800)


async def test_the_owner_duplicates_a_variant_to_another_size_from_the_panel(
    owner_client: AsyncClient,
) -> None:
    """«Размножить размером» copies the differences and takes only the new size from the panel."""
    variant_id = arranged_variant(width_mm=800, height_mm=600)

    response = await owner_client.post(
        _save_url(PRODUCT),
        _panel_post(width_mm=1200, height_mm=900, variant=str(variant_id), duplicate="1"),
    )

    assert response.status_code == HTTPStatus.OK
    sizes = {(variant["width_mm"], variant["height_mm"]) for variant in (_answer(response))["variants"]}
    assert sizes == {(800, 600), (1200, 900)}


async def test_the_owner_removes_a_variant_from_the_panel(owner_client: AsyncClient) -> None:
    """The panel takes the variant off the product and answers with what is left."""
    variant_id = arranged_variant(width_mm=800, height_mm=600)

    response = await owner_client.post(_delete_url(PRODUCT), {"variant": str(variant_id)})

    assert response.status_code == HTTPStatus.OK
    assert (_answer(response))["variants"] == []
    assert not await _variants().filter(id=variant_id).aexists()


async def test_the_storefront_price_stays_with_the_cheapest_of_the_added_variants(
    owner_client: AsyncClient,
) -> None:
    """A dearer variant does not move «цена от»: the storefront quotes the cheapest."""
    arranged_variant(width_mm=800, height_mm=600)

    await owner_client.post(_save_url(PRODUCT), _panel_post(width_mm=1200, height_mm=900, sort_order=1))

    assert (await _products().aget(id=PRODUCT)).price_from == Decimal(8820)


async def test_the_storefront_price_follows_the_cheapest_variant_off_the_product(
    owner_client: AsyncClient,
) -> None:
    """The mark the panel shows and the product's «цена от» are one and the same answer."""
    cheap = arranged_variant(width_mm=800, height_mm=600)
    await owner_client.post(_save_url(PRODUCT), _panel_post(width_mm=1200, height_mm=900, sort_order=1))

    listed = _answer(await owner_client.post(_delete_url(PRODUCT), {"variant": str(cheap)}))

    dearest = await _products().aget(id=PRODUCT)
    assert [variant["sets_product_price"] for variant in listed["variants"]] == [True]
    assert dearest.price_from == Decimal(listed["variants"][0]["price_label"].translate(_ONLY_DIGITS))


async def test_a_second_variant_of_the_same_configuration_is_refused_and_nothing_is_stored(
    owner_client: AsyncClient,
) -> None:
    """The panel shows the refusal in the owner's words: DUPLICATE_VARIANT."""
    arranged_variant(width_mm=800, height_mm=600)

    response = await owner_client.post(_save_url(PRODUCT), _panel_post())

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert (_answer(response))["error"] == REFUSAL_MESSAGES[DuplicateVariantError]
    assert await _variants().filter(product_id=PRODUCT).acount() == 1


async def test_a_size_above_the_input_limit_is_refused_by_the_panel(owner_client: AsyncClient) -> None:
    """The panel refuses what the command refuses, and writes nothing: VALIDATION_ERROR."""
    response = await owner_client.post(_save_url(PRODUCT), _panel_post(width_mm=MAX_SIDE_MM + 1))

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert (_answer(response))["error"] == variant_builder.OUTSIDE_THE_LIMITS
    assert not await _variants().filter(product_id=PRODUCT).aexists()


async def test_the_panel_names_in_words_what_a_variant_changes_about_the_product(
    owner_client: AsyncClient,
) -> None:
    """The row of a variant reads as a sentence, not as identifiers."""
    response = await owner_client.post(
        _save_url(PRODUCT),
        _panel_post(value=f"{BLADE.hex}:{GRAPHITE.hex}"),
    )

    assert response.status_code == HTTPStatus.OK
    answer = _answer(response)
    assert answer["variants"][0]["values_label"] == "Тип полотна: Графит"


async def test_the_panel_of_a_saved_product_is_not_a_form_and_its_fields_carry_no_names(
    owner_client: AsyncClient,
) -> None:
    """A nested form the browser would drop, and named fields the card would post (ADR-0011)."""
    response = await owner_client.get(_card_url(PRODUCT))

    shown = response.content.decode()
    panel = shown[shown.index('id="variant-builder"') : shown.index('id="variant-rows"')]

    assert "<form" not in panel
    assert 'name="' not in panel


def test_the_panel_script_waits_for_the_markup_it_drives() -> None:
    """Django prints the media in `<head>` without `defer`: the script starts on DOMContentLoaded."""
    source = PANEL_SCRIPT.read_text(encoding="utf-8")

    assert 'document.addEventListener("DOMContentLoaded"' in source


async def test_an_unsaved_product_has_no_variant_builder(owner_client: AsyncClient) -> None:
    """A variant of nobody's product does not exist, so the card of a new one offers no panel."""
    response = await owner_client.get(f"{CHANGELIST_URL}add/")

    shown = response.content.decode()

    assert "Предпосчитанные варианты" in shown
    assert 'id="variant-builder-form"' not in shown


async def test_a_product_that_declared_nothing_yet_is_refused_a_variant_in_words(
    owner_client: AsyncClient,
) -> None:
    """A variant of a product with nothing paid declared cannot be priced: INVALID_VARIANT_CONFIGURATION."""
    empty = arranged_product(name="Зеркало без объявленных значений")

    response = await owner_client.post(_save_url(empty), _panel_post())

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert (_answer(response))["error"] == REFUSAL_MESSAGES[InvalidVariantConfigurationError]
    assert not await _variants().filter(product_id=empty).aexists()


async def test_the_owner_types_the_price_of_a_variant_nothing_prices(owner_client: AsyncClient) -> None:
    """A mirror the studio buys framed is priced by hand, and the panel says whose price it shows (ADR-0017)."""
    empty = arranged_product(name="Зеркало в багете")

    saved = _answer(await owner_client.post(_save_url(empty), _panel_post(manual_price="24000")))

    assert [variant["price_label"] for variant in saved["variants"]] == ["24\u202f000\u202f₽"]
    assert [variant["price_is_manual"] for variant in saved["variants"]] == [True]


async def test_a_variant_the_panel_priced_itself_is_not_marked_as_the_owners(owner_client: AsyncClient) -> None:
    """The mark separates the typed price from the calculated one; without it the list tells them apart by nothing."""
    saved = _answer(await owner_client.post(_save_url(PRODUCT), _panel_post()))

    assert [variant["price_is_manual"] for variant in saved["variants"]] == [False]


async def test_a_typed_price_is_taken_down_to_the_kopeck_the_column_keeps(owner_client: AsyncClient) -> None:
    """The list must redraw the number the owner typed, not one the column rounded behind him."""
    saved = _answer(await owner_client.post(_save_url(PRODUCT), _panel_post(manual_price="24000.999")))

    assert [variant["price_label"] for variant in saved["variants"]] == ["24\u202f001\u202f₽"]


async def test_the_panel_refuses_a_price_that_is_not_a_number(owner_client: AsyncClient) -> None:
    """A price the panel could never have composed is refused in the owner's words."""
    response = await owner_client.post(_save_url(PRODUCT), _panel_post(manual_price="дорого"))

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert (_answer(response))["error"] == variant_builder.NOT_A_PRICE


async def test_the_panel_refuses_a_variant_of_a_product_nobody_entered(owner_client: AsyncClient) -> None:
    """A panel address carrying an identifier nobody issued: PRODUCT_NOT_FOUND."""
    response = await owner_client.post(_save_url(uuid4()), _panel_post())

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert (_answer(response))["error"] == REFUSAL_MESSAGES[ProductNotFoundError]


async def test_the_panel_answers_nobody_who_may_not_change_the_product(clerk_client: AsyncClient) -> None:
    """Signing in is not the permission: the panel writes the product, and staff without it is refused."""
    response = await clerk_client.post(_save_url(PRODUCT), _panel_post())

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert (_answer(response))["error"] == variant_builder.NOT_YOURS
    assert await _variants().filter(product_id=PRODUCT).acount() == 0


async def test_the_panel_answers_nobody_who_is_not_signed_in() -> None:
    """The three answers of the panel sit behind the same login as the card."""
    response = await AsyncClient().get(_price_url(PRODUCT))

    assert response.status_code == HTTPStatus.FOUND
    assert response.headers["location"].startswith("/admin/login/")


def test_a_whole_sum_is_written_without_kopecks() -> None:
    """Thousands stand apart and a whole sum carries no kopecks at all (§12.4)."""
    written = variant_builder.money_label(Decimal("8820.00"))

    assert written == WORKBOOK_PRICE


def test_a_sum_with_kopecks_keeps_them() -> None:
    """A price that is not whole is not rounded away in the writing of it (§12.4)."""
    written = variant_builder.money_label(Decimal("1234567.50"))

    assert written == "1\u202f234\u202f567,50\u202f₽"
