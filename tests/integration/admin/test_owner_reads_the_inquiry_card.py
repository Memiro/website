"""The owner opens an inquiry and reads its positions the way the manager email says them (ticket 03)."""

import re
from collections.abc import AsyncIterator
from http import HTTPStatus

import pytest
from django.test import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from tests.common.factory.catalog import LEGACY_INQUIRY, PRODUCT, SPECIFIED_INQUIRY
from tests.integration.prime import prime_legacy_inquiry, prime_specified_inquiry

pytestmark = pytest.mark.usefixtures("admin_site", "primed_inquiries")

APP = "memiro"
INQUIRY_CARD_URL = f"/admin/{APP}/inquiry/{SPECIFIED_INQUIRY}/change/"
LEGACY_CARD_URL = f"/admin/{APP}/inquiry/{LEGACY_INQUIRY}/change/"
PRODUCT_CARD_URL = f"/admin/{APP}/product/{PRODUCT}/change/"


@pytest.fixture(scope="module")
async def primed_inquiries(admin_database_url: str, primed_catalog: None) -> AsyncIterator[None]:  # noqa: ARG001
    """Put the two inquiries under test into the admin's database once for the module."""
    engine = create_async_engine(admin_database_url)
    try:
        await prime_specified_inquiry(engine)
        await prime_legacy_inquiry(engine)
        yield
    finally:
        await engine.dispose()


async def test_the_owner_opens_an_inquiry_card_with_the_positions_inlined(
    owner_client: AsyncClient,
) -> None:
    """The card shows the contacts and every position with its specification, price and wish."""
    response = await owner_client.get(INQUIRY_CARD_URL)

    page = response.content.decode()
    assert response.status_code == HTTPStatus.OK
    assert "Мария" in page
    assert "+79990000002" in page
    assert "maria@example.test" in page
    assert "2026-01-01" in page
    assert "800 × 600 мм" in page  # noqa: RUF001
    assert "Тип полотна: Серебро" in page  # noqa: RUF001
    assert "Крепление: С креплением" in page  # noqa: RUF001
    assert "Цена: 8 820 ₽" in page
    assert "Повесить над комодом" in page


async def test_a_hidden_price_and_a_refused_choice_read_in_the_words_of_the_email(
    owner_client: AsyncClient,
) -> None:
    """A HIDDEN price is marked as unseen by the customer and a refusal is named in words, never by code."""
    response = await owner_client.get(INQUIRY_CARD_URL)

    page = response.content.decode()
    assert "Цена: 10 020 ₽ (покупателю не показана)" in page
    assert "Цена не рассчитана: расчёт не взял этот выбор" in page
    assert "SELECTION_NOT_PRICEABLE" not in page
    assert "Итог" not in page
    assert "18 840" not in page


async def test_a_position_of_a_removed_product_reads_without_a_link_to_it(
    owner_client: AsyncClient,
) -> None:
    """A position keeps its name after its product is gone; only positions of a living product link to its card."""
    response = await owner_client.get(INQUIRY_CARD_URL)

    page = response.content.decode()
    assert "Зеркало из прошлого каталога" in page
    assert len(re.findall(re.escape(PRODUCT_CARD_URL), page)) == 2  # noqa: PLR2004  # the priced and the refused position


async def test_an_inquiry_stored_before_the_whole_specification_opens_as_it_was(
    owner_client: AsyncClient,
) -> None:
    """An old inquiry with only the chosen value on its position opens and shows that value alone (rule 21)."""
    response = await owner_client.get(LEGACY_CARD_URL)

    page = response.content.decode()
    assert response.status_code == HTTPStatus.OK
    assert "Тип полотна: Графит" in page
    assert "Рама:" not in page
    assert "Цена: 10 020 ₽" in page


async def test_the_owner_is_offered_no_form_to_edit_an_inquiry(
    owner_client: AsyncClient,
) -> None:
    """The card is a reading: nothing on it is an input and nothing saves."""
    response = await owner_client.get(INQUIRY_CARD_URL)

    page = response.content.decode()
    assert 'name="_save"' not in page
    assert 'name="name"' not in page


async def test_the_inquiry_list_still_narrows_by_source_and_date(
    owner_client: AsyncClient,
) -> None:
    """The changelist keeps its filters next to the card."""
    response = await owner_client.get(f"/admin/{APP}/inquiry/?source__exact=SELECTION")

    page = response.content.decode()
    assert response.status_code == HTTPStatus.OK
    assert "Мария" in page
    assert "?source__exact=FREE_FORM" in page
    assert "created_at__gte=" in page
