import pytest
from dishka import AsyncContainer
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from memiro.adapters.smtp.config import EmailConfig
from memiro.adapters.smtp.inquiry_notification import SMTPInquiryNotificationBus
from memiro.application.common.customer_selection import Selection
from memiro.application.common.gateway.inquiry import InquiryGateway
from memiro.application.submit_inquiry import InquiryItemForm, InquirySource, SubmitInquiry, SubmitInquiryForm
from tests.common.factory.catalog import BLADE, GRAPHITE, PRODUCT
from tests.integration.api_client import ApiClient

pytestmark = pytest.mark.usefixtures("catalog")

_ONE_ITEM_FORM = SubmitInquiryForm(
    source=InquirySource.SELECTION,
    name="Anna",
    phone="+79990000000",
    email=None,
    consent=True,
    comment="",
    items=[InquiryItemForm(product_id=PRODUCT, width_mm=800, height_mm=600, selections=[], wish="")],
)


async def test_a_committed_inquiry_uses_the_enabled_port_configured_smtp_channel_to_send_each_saved_snapshot(
    notifying_api_client: ApiClient,
    smtp_server: tuple[int, list[str]],
) -> None:
    """A submitted inquiry sends a separate snapshot for every configured mirror."""
    form = SubmitInquiryForm(
        source=InquirySource.SELECTION,
        name="Anna",
        phone="+79990000000",
        email="anna@example.test",
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
            InquiryItemForm(product_id=PRODUCT, width_mm=900, height_mm=900, selections=[], wish=""),
        ],
    )

    response = await notifying_api_client.submit_inquiry(form)

    _, received_emails = smtp_server

    assert response.assert_status(200).ensure_content().id
    assert len(received_emails) == 1
    assert "Заявка" in received_emails[0]
    assert "Зеркало 1" in received_emails[0]
    assert "Зеркало 2" in received_emails[0]
    assert "800 × 600 мм" in received_emails[0]
    assert "Графит" in received_emails[0]
    assert "Warm light" in received_emails[0]
    assert "PRICED" in received_emails[0]
    assert "10 100" in received_emails[0]


async def test_a_switched_off_channel_sends_nothing(
    silent_api_client: ApiClient,
    smtp_server: tuple[int, list[str]],
) -> None:
    """An email channel switched off by configuration delivers no message at all."""
    response = await silent_api_client.submit_inquiry(_ONE_ITEM_FORM)

    _, received_emails = smtp_server

    assert response.assert_status(200).ensure_content().id
    assert received_emails == []


async def test_an_smtp_failure_keeps_the_saved_inquiry(
    failing_api_client: ApiClient,
    failing_app: FastAPI,
) -> None:
    """An unavailable SMTP channel does not roll back a submitted inquiry."""
    form = SubmitInquiryForm(
        source=InquirySource.SELECTION,
        name="Anna",
        phone="+79990000000",
        email=None,
        consent=True,
        comment="",
        items=[InquiryItemForm(product_id=PRODUCT, width_mm=800, height_mm=600, selections=[], wish="")],
    )

    created = (await failing_api_client.submit_inquiry(form)).assert_status(200).ensure_content()
    container: AsyncContainer = failing_app.state.dishka_container
    async with container() as request:
        gateway: InquiryGateway = await request.get(InquiryGateway)
        inquiry = await gateway.get(created.id)

    assert inquiry is not None
    assert inquiry.items[0].calculated_price is not None


async def test_an_empty_manager_address_keeps_the_saved_inquiry(
    capfd: pytest.CaptureFixture[str],
    empty_address_api_client: ApiClient,
    empty_address_app: FastAPI,
) -> None:
    """An empty manager address skips mail without losing the submitted inquiry."""
    form = SubmitInquiryForm(
        source=InquirySource.SELECTION,
        name="Anna",
        phone="+79990000000",
        email=None,
        consent=True,
        comment="",
        items=[InquiryItemForm(product_id=PRODUCT, width_mm=800, height_mm=600, selections=[], wish="")],
    )

    created = (await empty_address_api_client.submit_inquiry(form)).assert_status(200).ensure_content()
    container: AsyncContainer = empty_address_app.state.dishka_container
    async with container() as request:
        gateway: InquiryGateway = await request.get(InquiryGateway)
        inquiry = await gateway.get(created.id)

    logs = capfd.readouterr().err

    assert inquiry is not None
    assert "Manager email notification skipped because no recipient is configured" in logs
    assert "Anna" not in logs
    assert "+79990000000" not in logs


async def test_the_manager_email_is_sent_without_holding_the_request_transaction(
    request_container: AsyncContainer,
) -> None:
    """The pooled connection is released before the blocking send, so a hung host cannot drain the pool."""
    held_transaction: list[bool] = []
    session: AsyncSession = await request_container.get(AsyncSession)
    submit: SubmitInquiry = await request_container.get(SubmitInquiry)
    created = await submit.execute(_ONE_ITEM_FORM)
    bus = SMTPInquiryNotificationBus(
        EmailConfig(enabled=True, from_address="site@example.test", manager_address="manager@example.test"),
        await request_container.get(InquiryGateway),
        session,
        lambda _config, _message: held_transaction.append(session.in_transaction()),
    )

    await bus.notify(created.id)

    assert held_transaction == [False]
