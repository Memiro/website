"""Подменный транспорт уведомлений о заявке для тестов."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from memiro.leads.models import Lead


class RecordingNotifier:
    """Складывает заявки в список вместо отправки в Telegram."""

    sent: ClassVar[list[Lead]] = []

    def send(self, lead: Lead) -> None:
        type(self).sent.append(lead)


class FailingNotifier:
    """Транспорт, который всегда падает: заявка не должна теряться."""

    def send(self, lead: Lead) -> None:  # noqa: ARG002
        message = "Telegram недоступен"
        raise RuntimeError(message)
