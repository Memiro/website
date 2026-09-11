"""The owner keeps the catalogue from the product card, and every write goes through an interactor (ADR-0012).

Sections are the exception the ticket names: content without rules is written
straight to the mirror, one screen away from the products that use it.
"""

import re
from html import unescape
from http import HTTPStatus
from types import ModuleType
from typing import Any, cast
from uuid import uuid4

import pytest
from django.apps import apps
from django.db.models import Manager
from django.test import AsyncClient

from memiro.application.errors.catalog import (
    AttributeValueNotFoundError,
    ProductNotFoundError,
    ProductSlugTakenError,
)
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, CategoryId, ProductId
from memiro.entities.errors.product import InvalidProductSlugError, ProductSectionNotEmptyError
from memiro.presentation.django_admin.refusals import REFUSAL_MESSAGES
from memiro.presentation.django_admin.section_card import stamped_now
from tests.common.factory.catalog import ALUMINIUM, BACKLIGHT, BLADE, CONTOUR, FRAME, PRODUCT, SILVER
from tests.integration.admin.arrange import (
    arranged_attribute,
    arranged_product,
    category_post,
    product_post,
    value_form,
)

pytestmark = pytest.mark.usefixtures("admin_site", "primed_catalog")

APP = "memiro"
CHANGELIST_URL = f"/admin/{APP}/product/"
ADD_URL = f"{CHANGELIST_URL}add/"
CATEGORY_CHANGELIST_URL = f"/admin/{APP}/category/"
CATEGORY_ADD_URL = f"{CATEGORY_CHANGELIST_URL}add/"
LOGIN_URL = "/admin/login/"
# The demo mirror carries two photos, and its card posts their inline back.
DEMO_PHOTOS = 2
# Every refusal a product screen can meet, spelled out rather than collected
# from the modules: a code missing from the table is not a 500 but a silence.
PRODUCT_REFUSALS = (
    ProductNotFoundError,
    ProductSlugTakenError,
    InvalidProductSlugError,
    ProductSectionNotEmptyError,
    AttributeValueNotFoundError,
)


def _wording() -> ModuleType:
    """Reach the screen's own sentences: the module of the card may not be imported before ``django.setup()``."""
    from memiro.presentation.django_admin import admin  # noqa: PLC0415

    return admin


def _warning(page: str) -> str:
    """Read what the screen warned about after the save, the markup of the message list stripped."""
    said = re.search(r'<li class="warning">(.*?)</li>', page, flags=re.DOTALL)
    return unescape(said.group(1)).strip() if said else ""


async def _value_of(attribute_id: AttributeId) -> AttributeValueId:
    """Read back the single dictionary row of an attribute a test arranged."""
    values = cast("Manager[Any]", apps.get_model(APP, "AttributeValue").objects)
    value = await values.aget(attribute_id=attribute_id)
    return cast("AttributeValueId", value.id)


def _products() -> Manager[Any]:
    """Reach the product mirror; the app registry is only ready once Django is configured."""
    return cast("Manager[Any]", apps.get_model(APP, "Product").objects)


def _categories() -> Manager[Any]:
    """Reach the section mirror; the app registry is only ready once Django is configured."""
    return cast("Manager[Any]", apps.get_model(APP, "Category").objects)


def _declarations() -> Manager[Any]:
    """Reach the declared values of the products; they have no changelist of their own."""
    return cast("Manager[Any]", apps.get_model(APP, "ProductDeclaredValue").objects)


async def _declared_by(product_id: ProductId) -> dict[AttributeId, AttributeValueId]:
    """Read the whole declared set of one product back, as the card claims to have left it."""
    declared = _declarations().filter(product_id=product_id)
    return {value.attribute_id: value.value_id async for value in declared}


def _card_url(product_id: ProductId) -> str:
    return f"{CHANGELIST_URL}{product_id}/change/"


def _delete_url(product_id: ProductId) -> str:
    return f"{CHANGELIST_URL}{product_id}/delete/"


async def _arranged_section(*, name: str, slug: str) -> CategoryId:
    """Enter one more section the way its own screen does: straight into the mirror."""
    stamped = stamped_now()
    section = await _categories().acreate(name=name, slug=slug, sort_order=0, created_at=stamped, updated_at=stamped)
    return cast("CategoryId", section.id)


async def test_the_owner_enters_a_product_into_a_section_from_the_card(owner_client: AsyncClient) -> None:
    """The card of a new product reaches the domain as the command that creates it."""
    response = await owner_client.post(ADD_URL, product_post(name="Круглое зеркало", description="Без рамы."))

    assert response.status_code == HTTPStatus.FOUND
    created = await _products().aget(name="Круглое зеркало")
    assert created.slug == "krugloe-zerkalo"


async def test_the_owner_restates_the_root_and_the_declared_values_of_a_saved_product(
    owner_client: AsyncClient,
) -> None:
    """One save of the card carries both halves: the renamed root and the whole declared set."""
    product_id = arranged_product(name="Зеркало для прихожей")

    response = await owner_client.post(
        _card_url(product_id),
        product_post(
            name="Зеркало в прихожей",
            slug="zerkalo-dlya-prihozhey",
            declared=[(BLADE, str(SILVER)), (FRAME, str(ALUMINIUM))],
        ),
    )

    assert response.status_code == HTTPStatus.FOUND
    assert (await _products().aget(id=product_id)).name == "Зеркало в прихожей"
    assert await _declared_by(product_id) == {BLADE: SILVER, FRAME: ALUMINIUM}


async def test_the_owner_moves_an_empty_product_to_another_section_from_the_card(
    owner_client: AsyncClient,
) -> None:
    """A move on its own is one save: the values of the new section are declared by the next one."""
    section = await _arranged_section(name="Тумбы", slug="tumby")
    product_id = arranged_product(name="Зеркало над тумбой")

    response = await owner_client.post(
        _card_url(product_id),
        product_post(name="Зеркало над тумбой", category=section),
    )

    assert response.status_code == HTTPStatus.FOUND
    assert (await _products().aget(id=product_id)).category_id == section
    assert await _declared_by(product_id) == {}


async def test_the_owner_removes_a_product_from_its_card(owner_client: AsyncClient) -> None:
    """Deletion from the card goes through the interactor that owns everything belonging to the product."""
    product_id = arranged_product(name="Зеркало на выброс")

    response = await owner_client.post(_delete_url(product_id), {"post": "yes"})

    assert response.status_code == HTTPStatus.FOUND
    assert not await _products().filter(id=product_id).aexists()


async def test_the_list_says_which_attributes_a_product_has_not_filled_in_yet(owner_client: AsyncClient) -> None:
    """A product declaring nothing names the attributes of its section instead of showing a price."""
    from memiro.presentation.django_admin.admin import UNDECLARED  # noqa: PLC0415  # after ``django.setup()``

    arranged_product(name="Зеркало без начинки")

    response = await owner_client.get(CHANGELIST_URL)

    shown = response.content.decode()
    assert UNDECLARED in shown
    assert "Тип полотна" in shown


async def test_the_list_says_when_a_complete_product_still_has_nothing_to_charge_for(
    owner_client: AsyncClient,
) -> None:
    """A section whose only attribute is unpaid leaves a complete product without a calculator."""
    from memiro.presentation.django_admin.admin import NOTHING_IS_PAID  # noqa: PLC0415  # after ``django.setup()``

    section = await _arranged_section(name="Бесплатное", slug="besplatnoe")
    product_id = arranged_product(name="Зеркало из воздуха")
    await _products().filter(id=product_id).aupdate(category_id=section)

    response = await owner_client.get(CHANGELIST_URL)

    assert NOTHING_IS_PAID in response.content.decode()


async def test_the_list_shows_the_price_the_catalogue_starts_from(owner_client: AsyncClient) -> None:
    """«Цена от» is a column of the list and nothing else: it is derived from the variants."""
    response = await owner_client.get(CHANGELIST_URL)

    assert "column-price_from" in response.content.decode()


async def test_the_owner_enters_a_section_from_its_own_card(owner_client: AsyncClient) -> None:
    """A section carries no rules, so its card writes the mirror directly (decision 3)."""
    response = await owner_client.post(CATEGORY_ADD_URL, category_post(name="Панно", slug="panno"))

    assert response.status_code == HTTPStatus.FOUND
    assert await _categories().filter(slug="panno").aexists()


async def test_the_owner_renames_and_then_removes_a_section(owner_client: AsyncClient) -> None:
    """The other three verbs of a section are Django's own: there is no interactor to ask."""
    section = await _arranged_section(name="Времянка", slug="vremyanka")

    await owner_client.post(
        f"{CATEGORY_CHANGELIST_URL}{section}/change/", category_post(name="Витрина", slug="vitrina")
    )
    await owner_client.post(f"{CATEGORY_CHANGELIST_URL}{section}/delete/", {"post": "yes"})

    assert not await _categories().filter(id=section).aexists()


async def test_a_card_that_moves_a_product_and_declares_values_at_once_comes_back_untouched(
    owner_client: AsyncClient,
) -> None:
    """The card carries the fields of the section being left, so the move and the values cannot ride together."""
    from memiro.presentation.django_admin.forms import MOVE_CARRIES_VALUES  # noqa: PLC0415  # after ``django.setup()``

    section = await _arranged_section(name="Полки", slug="polki")
    product_id = arranged_product(name="Зеркало на переезд")

    response = await owner_client.post(
        _card_url(product_id),
        product_post(name="Зеркало на переезд", category=section, declared=[(BLADE, str(SILVER))]),
    )

    assert MOVE_CARRIES_VALUES in response.content.decode()
    assert (await _products().aget(id=product_id)).category_id != section


async def test_a_stranger_writes_no_product_from_the_card() -> None:
    """An unauthenticated POST is sent to the login page and leaves the catalogue alone."""
    stranger = AsyncClient()

    response = await stranger.post(ADD_URL, product_post(name="Незваное зеркало"))

    assert response.headers["Location"].startswith(LOGIN_URL)
    assert not await _products().filter(name="Незваное зеркало").aexists()


async def test_only_the_screens_of_this_ticket_take_a_card_from_the_owner(owner_client: AsyncClient) -> None:
    """The refusal to write is lifted from the products and the sections, and from nothing else."""
    statuses = {
        url: (await owner_client.get(url)).status_code
        for url in (ADD_URL, CATEGORY_ADD_URL, f"/admin/{APP}/productvariant/add/")
    }

    assert statuses == {
        ADD_URL: HTTPStatus.OK,
        CATEGORY_ADD_URL: HTTPStatus.OK,
        f"/admin/{APP}/productvariant/add/": HTTPStatus.FORBIDDEN,
    }


def test_every_refusal_a_product_screen_can_meet_is_named_in_the_owner_s_words() -> None:
    """A code missing from the table shows «Запись отклонена.» and is invisible without this check."""
    named = REFUSAL_MESSAGES.keys()

    assert set(PRODUCT_REFUSALS) <= named


async def test_a_card_claiming_an_address_another_product_answers_on_comes_back_with_a_message(
    owner_client: AsyncClient,
) -> None:
    """PRODUCT_SLUG_TAKEN: the address belongs to the demo mirror, and nothing is stored."""
    response = await owner_client.post(
        ADD_URL,
        product_post(name="Второе зеркало в раме", slug="zerkalo-v-rame"),
        follow=True,
    )

    assert REFUSAL_MESSAGES[ProductSlugTakenError] in response.content.decode()
    assert not await _products().filter(name="Второе зеркало в раме").aexists()


async def test_moving_a_product_that_declares_anything_to_another_section_changes_nothing(
    owner_client: AsyncClient,
) -> None:
    """PRODUCT_SECTION_NOT_EMPTY: the demo mirror declares its values, so it stays where it is."""
    section = await _arranged_section(name="Шкафы", slug="shkafy")

    response = await owner_client.post(
        _card_url(PRODUCT),
        product_post(name="Зеркало в раме", slug="zerkalo-v-rame", category=section, photos=DEMO_PHOTOS),
        follow=True,
    )

    assert REFUSAL_MESSAGES[ProductSectionNotEmptyError] in response.content.decode()
    assert (await _products().aget(id=PRODUCT)).category_id != section


async def test_a_card_of_a_product_nobody_issued_is_not_found(owner_client: AsyncClient) -> None:
    """An identifier nobody issued names no card: the screen answers before the domain does."""
    response = await owner_client.post(_card_url(uuid4()), product_post(name="Ничьё"))

    assert response.status_code == HTTPStatus.FOUND
    assert response.headers["Location"] == "/admin/"


async def test_the_card_says_that_the_storefront_will_not_price_the_product(owner_client: AsyncClient) -> None:
    """Switching the backlight on made a dependent attribute applicable, and the card says so where it happened."""
    declared = await _declared_by(PRODUCT)
    declared[BACKLIGHT] = CONTOUR

    response = await owner_client.post(
        _card_url(PRODUCT),
        product_post(
            name="Зеркало в раме",
            slug="zerkalo-v-rame",
            photos=DEMO_PHOTOS,
            declared=[(attribute_id, str(value_id)) for attribute_id, value_id in declared.items()],
        ),
        follow=True,
    )

    assert response.status_code == HTTPStatus.OK
    warning = _warning(response.content.decode())
    assert warning.startswith(f"{_wording().WILL_NOT_PRICE} {_wording().UNDECLARED}")
    assert "Подогрев" in warning


async def test_a_card_the_calculator_is_happy_with_says_nothing(owner_client: AsyncClient) -> None:
    """The warning is a warning, not a summary of every save: a product that prices keeps the screen quiet."""
    section = await _arranged_section(name="Зеркала на заказ", slug="zerkala-na-zakaz")
    attribute = arranged_attribute(name="Полотно", values=[value_form(name="Серебряное")], category=section)
    value = await _value_of(attribute)
    # Entered first and declared after: a card of a product that does not
    # exist yet carries no fields of its section (``_card_form``). Followed,
    # so that what the screen said about it is read and gone.
    await owner_client.post(ADD_URL, product_post(name="Зеркало без рамы", category=section), follow=True)
    product_id = (await _products().aget(name="Зеркало без рамы")).id

    response = await owner_client.post(
        _card_url(product_id),
        product_post(name="Зеркало без рамы", category=section, declared=[(attribute, str(value))]),
        follow=True,
    )

    assert response.status_code == HTTPStatus.OK
    assert _warning(response.content.decode()) == ""
