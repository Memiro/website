import asyncio
import smtplib
import ssl
from collections.abc import Callable
from email.message import EmailMessage
from typing import override

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from memiro.adapters.smtp.config import EmailConfig, SMTPEncryption
from memiro.application.common.gateway.inquiry import InquiryGateway
from memiro.application.common.notification import InquiryNotificationBus
from memiro.entities.common.identifiers import InquiryId
from memiro.entities.common.money import Money
from memiro.entities.inquiry.entity import Inquiry, InquiryItem
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)

type Transport = Callable[[EmailConfig, EmailMessage], None]


def _smtp_client(config: EmailConfig) -> smtplib.SMTP | smtplib.SMTP_SSL:
    """Open SMTP using the encryption mode selected by configuration."""
    if config.encryption is SMTPEncryption.SSL:
        return smtplib.SMTP_SSL(
            config.host, config.port, timeout=config.timeout_seconds, context=ssl.create_default_context()
        )
    client = smtplib.SMTP(config.host, config.port, timeout=config.timeout_seconds)
    if config.encryption is SMTPEncryption.STARTTLS:
        client.starttls(context=ssl.create_default_context())
    return client


def smtp_transport(config: EmailConfig, message: EmailMessage) -> None:
    """Deliver one ready email through the configured encrypted SMTP transport."""
    with _smtp_client(config) as client:
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
    lines = [f"Зеркало {index}: {item.product_name}", f"Вердикт: {item.verdict.value}"]
    if item.configuration is not None:
        dimensions = item.configuration.dimensions
        lines.append(f"Размер: {dimensions.width.value} × {dimensions.height.value} мм")
        lines.extend(_configuration_lines(item))
    lines.append(f"Цена: {_money(item.calculated_price)}")
    if item.wish:
        lines.append(f"Пожелание: {item.wish}")
    return "\n".join(lines)


def _configuration_lines(item: InquiryItem) -> list[str]:
    """Render named selections retained in the item snapshot."""
    if item.configuration is None:
        return []
    return [
        f"{value.attribute_name}: {value.value_name if value.value_name is not None else value.quantity}"
        for value in item.configuration.values
    ]


def _money(value: Money | None) -> str:
    """Render a retained money value for a manager-facing email."""
    if value is None:
        return "не рассчитана"
    return f"{value.amount:,.2f}".replace(",", " ") + " ₽"


class SMTPInquiryNotificationBus(InquiryNotificationBus):
    """SMTP implementation of the manager notification channel."""

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
        """Send an email built exclusively from the saved inquiry snapshot."""
        if not self._config.manager_address:
            logger.warning("Manager email notification skipped because no recipient is configured")
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
