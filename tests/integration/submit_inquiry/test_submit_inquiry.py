from decimal import Decimal
from uuid import uuid4

import pytest
from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.common.customer_selection import Selection
from memiro.application.common.gateway.inquiry import InquiryGateway
from memiro.application.submit_inquiry import InquiryItemForm, InquirySource, SubmitInquiryForm
from memiro.entities.common.money import Money
from tests.common.factory.catalog import BLADE, GRAPHITE, PRODUCT
from tests.integration.api_client import ApiClient
from tests.integration.prime import prime_product_publication, update_attribute_value_rate_directly

pytestmark = pytest.mark.usefixtures("catalog")


async def test_a_customer_submits_multiple_configured_mirrors_in_one_inquiry(
    api_client: ApiClient,
) -> None:
    """A SELECTION inquiry stores every configured item in one aggregate."""
    form = SubmitInquiryForm(
        source=InquirySource.SELECTION,
        name="Anna",
        phone="+79990000000",
        email="anna@example.test",
        consent=True,
        comment="",
        items=[
            InquiryItemForm(product_id=PRODUCT, width_mm=800, height_mm=600, selections=[], wish=""),
            InquiryItemForm(
                product_id=PRODUCT,
                width_mm=900,
                height_mm=900,
                selections=[Selection(attribute_id=BLADE, value_id=GRAPHITE)],
                wish="Warm light",
            ),
        ],
    )

    response = await api_client.submit_inquiry(form)

    assert response.assert_status(200).ensure_content().id


async def test_an_inquiry_keeps_the_configuration_and_price_it_was_shown(
    api_client: ApiClient,
    engine: AsyncEngine,
    request_container: AsyncContainer,
) -> None:
    """An item snapshot does not change after its BLADE tariff changes."""
    form = SubmitInquiryForm(
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
                selections=[Selection(attribute_id=BLADE, value_id=GRAPHITE)],
                wish="Warm light",
            ),
        ],
    )

    created = (await api_client.submit_inquiry(form)).assert_status(200).ensure_content()
    await update_attribute_value_rate_directly(engine, GRAPHITE, Money(Decimal(1)))
    gateway: InquiryGateway = await request_container.get(InquiryGateway)
    inquiry = await gateway.get(created.id)

    assert inquiry is not None
    assert inquiry.items[0].calculated_price == Money(Decimal(10100))
    assert inquiry.items[0].configuration is not None
    assert inquiry.items[0].configuration.values[0].value_name == "Графит"


async def test_a_new_inquiry_rejects_the_historical_product_card_source(api_client: ApiClient) -> None:
    """A PRODUCT_CARD inquiry is rejected with INQUIRY_SOURCE_NOT_ACCEPTED before its item is read."""
    form = SubmitInquiryForm(
        source=InquirySource.PRODUCT_CARD,
        name="Anna",
        phone="+79990000000",
        email=None,
        consent=True,
        comment="",
        items=[InquiryItemForm(product_id=uuid4(), width_mm=800, height_mm=600, selections=[], wish="")],
    )

    response = await api_client.submit_inquiry(form)

    response.assert_error(400, "INQUIRY_SOURCE_NOT_ACCEPTED")


async def test_an_inquiry_without_consent_is_rejected_before_its_item_is_read(api_client: ApiClient) -> None:
    """A missing consent is rejected with CONSENT_REQUIRED without reading the named product."""
    form = SubmitInquiryForm(
        source=InquirySource.SELECTION,
        name="Anna",
        phone="+79990000000",
        email=None,
        consent=False,
        comment="",
        items=[InquiryItemForm(product_id=uuid4(), width_mm=800, height_mm=600, selections=[], wish="")],
    )

    response = await api_client.submit_inquiry(form)

    response.assert_error(400, "CONSENT_REQUIRED")


async def test_a_not_priceable_product_keeps_no_configuration_in_an_inquiry(
    api_client: ApiClient,
    engine: AsyncEngine,
    request_container: AsyncContainer,
) -> None:
    """A NOT_PRICEABLE item stores no configuration snapshot."""
    await prime_product_publication(engine, is_published=False)
    form = SubmitInquiryForm(
        source=InquirySource.SELECTION,
        name="Anna",
        phone="+79990000000",
        email=None,
        consent=True,
        comment="",
        items=[InquiryItemForm(product_id=PRODUCT, width_mm=800, height_mm=600, selections=[], wish="")],
    )

    created = (await api_client.submit_inquiry(form)).assert_status(200).ensure_content()
    gateway: InquiryGateway = await request_container.get(InquiryGateway)
    inquiry = await gateway.get(created.id)

    assert inquiry is not None
    assert inquiry.items[0].verdict.value == "NOT_PRICEABLE"
    assert inquiry.items[0].configuration is None
