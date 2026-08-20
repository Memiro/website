"""Уведомление владельца о заявке.

Транспорт подменяем: класс берётся из `settings.LEAD_NOTIFIER`, так что
тесты подставляют свой, а прод — Telegram. Падение транспорта не
отменяет заявку: она уже в журнале, уведомление — вторично.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING, Protocol

from django.conf import settings
from django.utils.module_loading import import_string

if TYPE_CHECKING:
    from memiro.leads.models import Lead

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
TIMEOUT_SECONDS = 5


class LeadNotifier(Protocol):
    """Транспорт уведомления о заявке."""

    def send(self, lead: Lead) -> None: ...


def lead_message(lead: Lead) -> str:
    """Текст уведомления: контакты, состав и комментарий одной пачкой."""
    lines = [
        f"Заявка №{lead.pk} ({lead.get_source_display()})",
        f"Имя: {lead.name}",
        f"Телефон: {lead.phone}",
    ]
    if lead.email:
        lines.append(f"E-mail: {lead.email}")
    items = list(lead.items.all())
    if items:
        lines.append("Товары:")
        lines += [
            f"— {item.product_name}, от {item.product_price} ₽"
            for item in items
        ]
    if lead.comment:
        lines.append(f"Комментарий: {lead.comment}")
    return "\n".join(lines)


class TelegramNotifier:
    """Отправка в Telegram; без токена и чата — только запись в лог."""

    def send(self, lead: Lead) -> None:
        token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_CHAT_ID
        if not token or not chat_id:
            logger.warning(
                "Telegram не настроен, заявка №%s без уведомления", lead.pk
            )
            return
        payload = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": lead_message(lead)}
        ).encode()
        request = urllib.request.Request(  # noqa: S310
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            data=payload,
            method="POST",
        )
        # Схема жёстко https://api.telegram.org, подстановки URL нет
        with urllib.request.urlopen(  # noqa: S310  # nosec B310
            request, timeout=TIMEOUT_SECONDS
        ) as response:
            answer = json.loads(response.read())
        if not answer.get("ok"):
            logger.error("Telegram отказал: %s", answer)


def notify(lead: Lead) -> None:
    """Уведомить владельца, не роняя приём заявки.

    Внутри try и загрузка транспорта: опечатка в `LEAD_NOTIFIER` — тоже
    сбой уведомления, а не повод отдать 500 на уже принятую заявку.
    """
    try:
        notifier: LeadNotifier = import_string(settings.LEAD_NOTIFIER)()
        notifier.send(lead)
    except Exception:
        logger.exception("Не удалось уведомить о заявке №%s", lead.pk)
