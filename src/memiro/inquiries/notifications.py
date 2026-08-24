"""Уведомление владельца о заявке.

Транспорт подменяем: класс берётся из `settings.INQUIRY_NOTIFIER`, так что
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
    from memiro.inquiries.models import Inquiry

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
TIMEOUT_SECONDS = 5


class InquiryNotifier(Protocol):
    """Транспорт уведомления о заявке."""

    def send(self, inquiry: Inquiry) -> None: ...


def inquiry_message(inquiry: Inquiry) -> str:
    """Текст уведомления: контакты, состав и комментарий одной пачкой."""
    lines = [
        f"Заявка №{inquiry.pk} ({inquiry.get_source_display()})",
        f"Имя: {inquiry.name}",
        f"Телефон: {inquiry.phone}",
    ]
    if inquiry.email:
        lines.append(f"E-mail: {inquiry.email}")
    items = list(inquiry.items.all())
    if items:
        lines.append("Товары:")
        lines += [
            f"— {item.product_name}, от {item.product_price} ₽"
            if item.product_price is not None
            # Менеджеру важно увидеть это в заявке, а не гадать
            else f"— {item.product_name}, цена не рассчитана"
            for item in items
        ]
    if inquiry.comment:
        lines.append(f"Комментарий: {inquiry.comment}")
    return "\n".join(lines)


class TelegramNotifier:
    """Отправка в Telegram; без токена и чата — только запись в лог."""

    def send(self, inquiry: Inquiry) -> None:
        token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_CHAT_ID
        if not token or not chat_id:
            logger.warning(
                "Telegram не настроен, заявка №%s без уведомления", inquiry.pk
            )
            return
        payload = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": inquiry_message(inquiry)}
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


def notify(inquiry: Inquiry) -> None:
    """Уведомить владельца, не роняя приём заявки.

    Внутри try и загрузка транспорта: опечатка в `INQUIRY_NOTIFIER` — тоже
    сбой уведомления, а не повод отдать 500 на уже принятую заявку.
    """
    try:
        notifier: InquiryNotifier = import_string(settings.INQUIRY_NOTIFIER)()
        notifier.send(inquiry)
    except Exception:
        logger.exception("Не удалось уведомить о заявке №%s", inquiry.pk)
