"""Integration checks that a corrupted inquiry row never loads silently (§8.5)."""

import pytest
from dishka import AsyncContainer
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.adapters.db.tables import inquiry_items_table
from memiro.application.common.gateway.inquiry import InquiryGateway
from memiro.application.submit_inquiry import InquiryItemForm, InquirySource, SubmitInquiryForm
from memiro.entities.common.identifiers import InquiryId
from tests.common.factory.catalog import PRODUCT
from tests.integration.api_client import ApiClient

pytestmark = pytest.mark.usefixtures("catalog")


def _form() -> SubmitInquiryForm:
    """Build a consented selection of one canonical priced item."""
    return SubmitInquiryForm(
        source=InquirySource.SELECTION,
        name="Anna",
        phone="+79990000000",
        email=None,
        consent=True,
        comment="",
        items=[
            InquiryItemForm(
                product_id=PRODUCT,
                width_mm=800,
                height_mm=600,
                selections=[],
                wish="",
            )
        ],
    )


async def _drop_the_stored_price(engine: AsyncEngine, inquiry_id: InquiryId) -> None:
    """Leave a priced position without its price through the named dishonest-state seam."""
    async with engine.begin() as connection:
        await connection.execute(
            update(inquiry_items_table)
            .where(inquiry_items_table.c.inquiry_id == inquiry_id)
            .values(calculated_price=None),
        )


async def _corrupt_the_stored_phone(engine: AsyncEngine, inquiry_id: InquiryId) -> None:
    """Store a number that is not a number through the named dishonest-state seam."""
    # Raw SQL on purpose: the column type refuses to flatten anything but a
    # ``Phone``, and the row under test is exactly what it could not have written.
    async with engine.begin() as connection:
        await connection.execute(
            text("UPDATE inquiries SET phone = 'x' WHERE id = :inquiry_id"),
            {"inquiry_id": inquiry_id},
        )


async def test_a_stored_position_whose_price_disappeared_does_not_load_silently(
    api_client: ApiClient,
    engine: AsyncEngine,
    request_container: AsyncContainer,
) -> None:
    """A row whose verdict disagrees with its price is a defect and leaves as a 500."""
    created = (await api_client.submit_inquiry(_form())).assert_status(200).ensure_content()
    await _drop_the_stored_price(engine, created.id)
    gateway: InquiryGateway = await request_container.get(InquiryGateway)

    with pytest.raises(RuntimeError, match="disagrees with the presence of a price"):
        await gateway.get(created.id)


async def test_a_stored_inquiry_with_a_corrupted_phone_does_not_load_silently(
    api_client: ApiClient,
    engine: AsyncEngine,
    request_container: AsyncContainer,
) -> None:
    """A stored number the studio could not dial is a defect of the row, not a refusal."""
    created = (await api_client.submit_inquiry(_form())).assert_status(200).ensure_content()
    await _corrupt_the_stored_phone(engine, created.id)
    gateway: InquiryGateway = await request_container.get(InquiryGateway)

    with pytest.raises(RuntimeError, match="corrupted phone number"):
        await gateway.get(created.id)
