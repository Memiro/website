from collections.abc import Sequence
from typing import override

import structlog

from memiro.application.common.notification import InquiryNotificationBus
from memiro.entities.common.identifiers import InquiryId
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)


class CompositeInquiryNotificationBus(InquiryNotificationBus):
    """Best-effort fan-out to the enabled manager notification channels."""

    def __init__(self, channels: Sequence[InquiryNotificationBus]) -> None:
        """Retain the configured channel list without exposing it to callers."""
        self._channels = tuple(channels)

    @override
    async def notify(self, inquiry_id: InquiryId) -> None:
        """Attempt every channel without changing the committed inquiry outcome."""
        for channel in self._channels:
            try:
                await channel.notify(inquiry_id)
            except Exception:  # noqa: BLE001 -- an external notification must never fail the inquiry.
                logger.warning("Inquiry notification delivery failed", channel=type(channel).__name__)
