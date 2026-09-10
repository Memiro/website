import asyncio
from collections.abc import Callable
from email.message import EmailMessage
from typing import override

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from memiro.adapters.common.inquiry_wording import price_words, size_words, specification_line
from memiro.adapters.smtp.client import smtp_client
from memiro.adapters.smtp.config import EmailConfig
from memiro.application.common.gateway.inquiry import InquiryGateway
from memiro.application.common.notification import InquiryNotificationBus
from memiro.entities.common.identifiers import InquiryId
from memiro.entities.inquiry.entity import Inquiry, InquiryItem
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)

type Transport = Callable[[EmailConfig, EmailMessage], None]


def smtp_transport(config: EmailConfig, message: EmailMessage) -> None:
    """Deliver one ready email through the configured encrypted SMTP transport."""
    with smtp_client(config) as client:
        if config.username:
            client.login(config.username, config.password)
        client.send_message(message)


def _message(inquiry: Inquiry, config: EmailConfig) -> EmailMessage:
    """Build the manager email from immutable aggregate data only."""
    message = EmailMessage()
    message["From"] = config.from_address
    message["To"] = config.manager_address
    message["Subject"] = f"Заявка {inquiry.id}"
    message.set_content(_body(inquiry))
    return message


def _body(inquiry: Inquiry) -> str:
    """Render every inquiry item as an independent manager specification."""
    contacts = f"Имя: {inquiry.name}\nТелефон: {inquiry.phone.value}\nEmail: {inquiry.email or 'не указан'}"
    if not inquiry.items:
        return f"Заявка\n{contacts}\n\nКомментарий:\n{inquiry.comment}"
    items = "\n\n".join(_item(index, item) for index, item in enumerate(inquiry.items, start=1))
    return f"Заявка\n{contacts}\n\n{items}"


def _item(index: int, item: InquiryItem) -> str:
    """Render one immutable mirror specification without fetching live data."""
    lines = [f"Зеркало {index}: {item.product_name}"]
    if item.configuration is not None:
        lines.append(f"Размер: {size_words(item.configuration.dimensions)}")
        lines.extend(specification_line(value) for value in item.configuration.values)
    lines.append(price_words(item.verdict, item.calculated_price))
    if item.wish:
        lines.append(f"Пожелание: {item.wish}")
    return "\n".join(lines)


class SMTPInquiryNotificationBus(InquiryNotificationBus):
    """Best-effort email delivery of a saved inquiry to the manager."""

    def __init__(
        self,
        config: EmailConfig,
        inquiry_gateway: InquiryGateway,
        session: AsyncSession,
        send: Transport,
    ) -> None:
        """Keep the SMTP configuration outside the application layer."""
        self._config = config
        self._inquiry_gateway = inquiry_gateway
        self._session = session
        self._send = send

    @override
    async def notify(self, inquiry_id: InquiryId) -> None:
        """Swallow every SMTP failure so the delivery cannot change the committed outcome."""
        try:
            await self._send_to_manager(inquiry_id)
        except Exception:
            logger.warning("Inquiry notification delivery failed", inquiry_id=str(inquiry_id), exc_info=True)

    async def _send_to_manager(self, inquiry_id: InquiryId) -> None:
        """Send an email built exclusively from the saved inquiry snapshot."""
        if not self._config.enabled:
            return
        if not self._config.manager_address:
            logger.warning("Manager email notification skipped because no recipient is configured")
            return
        if self._config.username and not self._config.password:
            logger.warning("Manager email notification skipped because no password is configured")
            return
        inquiry = await self._inquiry_gateway.get(inquiry_id)
        if inquiry is None:
            logger.warning("Manager email notification skipped because the saved inquiry is unavailable")
            return
        message = _message(inquiry, self._config)
        # The read above opened a fresh transaction on the request's pooled
        # connection, and ``smtplib``'s timeout is per socket operation: a hung
        # host would hold that connection idle-in-transaction for the whole
        # wait, and enough of them exhaust the pool for every other route.
        # Closing, not committing: a best-effort email must never be what
        # commits somebody else's pending work. Unlike a rollback, closing
        # detaches the loaded aggregate instead of expiring it, so the
        # interactor's own reads after this line stay in memory.
        await self._session.close()
        await asyncio.to_thread(self._send, self._config, message)
