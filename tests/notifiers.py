"""Подменный транспорт уведомлений о заявке для тестов."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from memiro.inquiries.models import Inquiry


class RecordingNotifier:
    """Складывает заявки в список вместо отправки в Telegram."""

    sent: ClassVar[list[Inquiry]] = []

    def send(self, inquiry: Inquiry) -> None:
        type(self).sent.append(inquiry)


class FailingNotifier:
    """Транспорт, который всегда падает: заявка не должна теряться."""

    def send(self, inquiry: Inquiry) -> None:  # noqa: ARG002
        message = "Telegram недоступен"
        raise RuntimeError(message)
