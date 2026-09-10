from decimal import Decimal
from email.message import EmailMessage

import pytest
from dishka import AsyncContainer
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from memiro.adapters.smtp.config import EmailConfig
from memiro.adapters.smtp.inquiry_notification import SMTPInquiryNotificationBus
from memiro.application.common.customer_selection import Selection
from memiro.application.common.gateway.inquiry import InquiryGateway
from memiro.application.submit_inquiry import InquiryItemForm, InquirySource, SubmitInquiry, SubmitInquiryForm
from memiro.entities.common.measure import Millimeters
from tests.common.factory.catalog import BACKLIGHT, BLADE, CONTOUR, CUTOUTS, GRAPHITE, LEGACY_INQUIRY, PRODUCT
from tests.common.mail import text_half
from tests.integration.api_client import ApiClient
from tests.integration.prime import (
    prime_hidden_calculated_price,
    prime_legacy_inquiry,
    prime_numeric_catalog,
    prime_product_without_paid_values,
    prime_production_limits,
)

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

_CAPTURED_CHANNEL = EmailConfig(
    enabled=True,
    password="app-password",
    from_address="site@example.test",
    manager_address="manager@example.test",
)

# The plain-text half word for word: the HTML half is new, this one must not move.
_ONE_ITEM_TEXT = """Заявка
Имя: Anna
Телефон: +79990000000
Email: не указан

Зеркало 1: Зеркало в раме
Размер: 800 × 600 мм
Тип полотна: Серебро
Форма: Прямоугольное
Рама: Алюминий
Подсветка: Без подсветки
Крепление: С креплением
Цена: 8 820 ₽
"""

# Mirror of price_product in entities/pricing/pricing_service.py, by hand:
# 0.48 m2 x 4500 + 2.8 lm x 2200 + 500 = 8 820 for the canonical mirror and
# 0.81 m2 x 7000 + 3.6 lm x 2200 + 500 = 14 090 for the graphite one; their
# sum, 22 910, is exactly what the manager must not read (rule 18).
_CANONICAL_PRICE_LINE = "Цена: 8 820 ₽"
_GRAPHITE_PRICE_LINE = "Цена: 14 090 ₽"
_SUM_OF_THE_TWO = "22 910"


def _form(*items: InquiryItemForm) -> SubmitInquiryForm:
    """Build a consented selection of the given items."""
    return SubmitInquiryForm(
        source=InquirySource.SELECTION,
        name="Anna",
        phone="+79990000000",
        email="anna@example.test",
        consent=True,
        comment="",
        items=list(items),
    )


async def test_a_committed_inquiry_uses_the_enabled_port_configured_smtp_channel_to_send_each_saved_snapshot(
    notifying_api_client: ApiClient,
    smtp_server: tuple[int, list[str]],
) -> None:
    """A submitted inquiry sends a separate specification for every configured mirror, in words and without a sum."""
    form = _form(
        InquiryItemForm(product_id=PRODUCT, width_mm=800, height_mm=600, selections=[], wish=""),
        InquiryItemForm(
            product_id=PRODUCT,
            width_mm=900,
            height_mm=900,
            selections=[Selection(attribute_id=BLADE, value_id=GRAPHITE)],
            wish="Warm light",
        ),
    )

    response = await notifying_api_client.submit_inquiry(form)

    _, received_emails = smtp_server

    assert response.assert_status(200).ensure_content().id
    assert len(received_emails) == 1
    email = received_emails[0]
    assert "Заявка" in email
    assert "Зеркало 1: Зеркало в раме" in email
    assert "Зеркало 2: Зеркало в раме" in email
    assert "Размер: 800 × 600 мм" in email
    assert "Размер: 900 × 900 мм" in email
    assert "Тип полотна: Серебро" in email
    assert "Тип полотна: Графит" in email
    assert "Рама: Алюминий" in email
    assert "Подсветка: Без подсветки" in email
    assert "Пожелание: Warm light" in email
    assert _CANONICAL_PRICE_LINE in email
    assert _GRAPHITE_PRICE_LINE in email
    assert "PRICED" not in email
    assert _SUM_OF_THE_TWO not in email
    assert "Итог" not in email


async def test_a_hidden_price_reaches_the_manager_marked_as_unseen_by_the_customer(
    notifying_api_client: ApiClient,
    engine: AsyncEngine,
    smtp_server: tuple[int, list[str]],
) -> None:
    """A HIDDEN price is printed with the remark that the customer was never shown it (rule 19)."""
    await prime_hidden_calculated_price(engine)

    response = await notifying_api_client.submit_inquiry(_ONE_ITEM_FORM)

    _, received_emails = smtp_server

    assert response.assert_status(200).ensure_content().id
    assert "Цена: 8 820 ₽ (покупателю не показана)" in received_emails[0]
    assert "HIDDEN" not in received_emails[0]


async def test_a_size_beyond_production_reaches_the_manager_in_words(
    notifying_api_client: ApiClient,
    engine: AsyncEngine,
    smtp_server: tuple[int, list[str]],
) -> None:
    """A BEYOND_LIMITS position names its reason in words, its specification still printed."""
    await prime_production_limits(
        engine,
        max_long_side_mm=Millimeters(value=700),
        max_short_side_mm=Millimeters(value=500),
    )

    response = await notifying_api_client.submit_inquiry(_ONE_ITEM_FORM)

    _, received_emails = smtp_server

    assert response.assert_status(200).ensure_content().id
    assert "Цена не рассчитана: размер за пределом производства" in received_emails[0]
    assert "Тип полотна: Серебро" in received_emails[0]
    assert "BEYOND_LIMITS" not in received_emails[0]


async def test_a_choice_the_calculation_refused_reaches_the_manager_in_words(
    notifying_api_client: ApiClient,
    smtp_server: tuple[int, list[str]],
) -> None:
    """A SELECTION_NOT_PRICEABLE position names its reason in words, the refused choice in its specification."""
    form = _form(
        InquiryItemForm(
            product_id=PRODUCT,
            width_mm=800,
            height_mm=600,
            selections=[Selection(attribute_id=BACKLIGHT, value_id=CONTOUR)],
            wish="",
        ),
    )

    response = await notifying_api_client.submit_inquiry(form)

    _, received_emails = smtp_server

    assert response.assert_status(200).ensure_content().id
    assert "Цена не рассчитана: расчёт не взял этот выбор" in received_emails[0]
    assert "Подсветка: Контурная" in received_emails[0]
    assert "SELECTION_NOT_PRICEABLE" not in received_emails[0]


async def test_a_product_without_a_calculation_reaches_the_manager_without_a_specification(
    notifying_api_client: ApiClient,
    engine: AsyncEngine,
    smtp_server: tuple[int, list[str]],
) -> None:
    """A NOT_PRICEABLE position says so in words and prints neither size nor values (rule 8)."""
    await prime_product_without_paid_values(engine)

    response = await notifying_api_client.submit_inquiry(_ONE_ITEM_FORM)

    _, received_emails = smtp_server

    assert response.assert_status(200).ensure_content().id
    assert "Товар без расчёта" in received_emails[0]
    assert "Размер" not in received_emails[0]
    assert "NOT_PRICEABLE" not in received_emails[0]


async def test_a_count_reaches_the_manager_as_the_customer_typed_it(
    notifying_api_client: ApiClient,
    engine: AsyncEngine,
    smtp_server: tuple[int, list[str]],
) -> None:
    """A numeric value prints in the customer's units, not in the scale the database keeps it in."""
    await prime_numeric_catalog(engine)
    two_and_a_half = Selection(attribute_id=CUTOUTS, quantity=Decimal("2.5"))
    form = _form(InquiryItemForm(product_id=PRODUCT, width_mm=800, height_mm=600, selections=[two_and_a_half], wish=""))

    response = await notifying_api_client.submit_inquiry(form)

    _, received_emails = smtp_server

    assert response.assert_status(200).ensure_content().id
    assert "Вырезы: 2.5" in received_emails[0]
    assert "2.5000" not in received_emails[0]


async def test_a_snapshot_stored_before_the_whole_specification_is_printed_as_it_was(
    engine: AsyncEngine,
    request_container: AsyncContainer,
) -> None:
    """An old position with only the chosen value prints that value and nothing invented (rule 21)."""
    await prime_legacy_inquiry(engine)
    sent: list[EmailMessage] = []
    bus = SMTPInquiryNotificationBus(
        _CAPTURED_CHANNEL,
        await request_container.get(InquiryGateway),
        await request_container.get(AsyncSession),
        lambda _config, message: sent.append(message),
    )

    await bus.notify(LEGACY_INQUIRY)

    body = text_half(sent[0])
    assert "Зеркало 1: Зеркало в раме" in body
    assert "Размер: 800 × 600 мм" in body
    assert "Тип полотна: Графит" in body
    assert "Рама" not in body
    assert "Цена: 10 020 ₽" in body
    assert "Пожелание: Тёплый свет" in body


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
    created = (await failing_api_client.submit_inquiry(_ONE_ITEM_FORM)).assert_status(200).ensure_content()
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
    created = (await empty_address_api_client.submit_inquiry(_ONE_ITEM_FORM)).assert_status(200).ensure_content()
    container: AsyncContainer = empty_address_app.state.dishka_container
    async with container() as request:
        gateway: InquiryGateway = await request.get(InquiryGateway)
        inquiry = await gateway.get(created.id)

    logs = capfd.readouterr().err

    assert inquiry is not None
    assert "Manager email notification skipped because no recipient is configured" in logs
    assert "Anna" not in logs
    assert "+79990000000" not in logs


async def test_an_account_without_a_password_keeps_the_saved_inquiry_and_stays_off_the_wire(
    capfd: pytest.CaptureFixture[str],
    passwordless_api_client: ApiClient,
    passwordless_app: FastAPI,
    smtp_server: tuple[int, list[str]],
) -> None:
    """An SMTP account without a password skips mail before touching the network, the inquiry saved."""
    created = (await passwordless_api_client.submit_inquiry(_ONE_ITEM_FORM)).assert_status(200).ensure_content()
    container: AsyncContainer = passwordless_app.state.dishka_container
    async with container() as request:
        gateway: InquiryGateway = await request.get(InquiryGateway)
        inquiry = await gateway.get(created.id)

    _, received_emails = smtp_server
    logs = capfd.readouterr().err

    assert inquiry is not None
    assert received_emails == []
    assert "Manager email notification skipped because no password is configured" in logs
    assert "Anna" not in logs
    assert "+79990000000" not in logs


async def test_the_manager_email_carries_the_text_and_an_html_reading_of_the_same_snapshot(
    request_container: AsyncContainer,
) -> None:
    """The email has a plain-text half, unchanged, and an HTML half the manager's client prefers."""
    sent: list[EmailMessage] = []
    submit: SubmitInquiry = await request_container.get(SubmitInquiry)
    created = await submit.execute(_ONE_ITEM_FORM)
    bus = SMTPInquiryNotificationBus(
        _CAPTURED_CHANNEL,
        await request_container.get(InquiryGateway),
        await request_container.get(AsyncSession),
        lambda _config, message: sent.append(message),
    )

    await bus.notify(created.id)

    message = sent[0]
    html = message.get_body(preferencelist=("html",))
    assert message.get_content_type() == "multipart/alternative"
    assert text_half(message) == _ONE_ITEM_TEXT
    assert html is not None
    assert html.get_content_type() == "text/html"


async def test_the_html_half_links_the_phone_and_the_email_from_the_snapshot(
    request_container: AsyncContainer,
) -> None:
    """The manager dials and writes back from the letter: tel and mailto links carry the saved contacts."""
    sent: list[EmailMessage] = []
    submit: SubmitInquiry = await request_container.get(SubmitInquiry)
    created = await submit.execute(
        _form(InquiryItemForm(product_id=PRODUCT, width_mm=800, height_mm=600, selections=[], wish=""))
    )
    bus = SMTPInquiryNotificationBus(
        _CAPTURED_CHANNEL,
        await request_container.get(InquiryGateway),
        await request_container.get(AsyncSession),
        lambda _config, message: sent.append(message),
    )

    await bus.notify(created.id)

    html = sent[0].get_body(preferencelist=("html",))
    assert html is not None
    assert 'href="tel:+79990000000"' in html.get_content()
    assert 'href="mailto:anna@example.test"' in html.get_content()


async def test_the_manager_email_is_sent_without_holding_the_request_transaction(
    request_container: AsyncContainer,
) -> None:
    """The pooled connection is released before the blocking send, so a hung host cannot drain the pool."""
    held_transaction: list[bool] = []
    session: AsyncSession = await request_container.get(AsyncSession)
    submit: SubmitInquiry = await request_container.get(SubmitInquiry)
    created = await submit.execute(_ONE_ITEM_FORM)
    bus = SMTPInquiryNotificationBus(
        _CAPTURED_CHANNEL,
        await request_container.get(InquiryGateway),
        session,
        lambda _config, _message: held_transaction.append(session.in_transaction()),
    )

    await bus.notify(created.id)

    assert held_transaction == [False]
