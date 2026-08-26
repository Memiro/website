"""Подменный транспорт уведомлений о заявке для тестов."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from django.core.mail.backends.base import BaseEmailBackend

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.core.mail import EmailMessage

    from memiro.inquiries.models import Inquiry


class RecordingNotifier:
    """Складывает заявки в список вместо отправки письма."""

    sent: ClassVar[list[Inquiry]] = []

    def send(self, inquiry: Inquiry) -> None:
        type(self).sent.append(inquiry)


class FailingNotifier:
    """Транспорт, который всегда падает: заявка не должна теряться."""

    def send(self, inquiry: Inquiry) -> None:  # noqa: ARG002
        message = "Транспорт уведомления недоступен"
        raise RuntimeError(message)


class FailingEmailBackend(BaseEmailBackend):
    """Почтовый бэкенд, который всегда падает: SMTP чужой и ненадёжный.

    Заявка уже в журнале, и сбой отправки не должен возвращаться
    посетителю ошибкой (тикет 19).
    """

    def send_messages(
        self,
        email_messages: Sequence[EmailMessage],  # noqa: ARG002
    ) -> int:
        message = "SMTP недоступен"
        raise RuntimeError(message)
