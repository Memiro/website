"""Уведомление менеджера о заявке.

Транспорт подменяем: класс берётся из `settings.INQUIRY_NOTIFIER`, так что
тесты подставляют свой, а прод — почту. Падение транспорта не отменяет
заявку: она уже в журнале, уведомление — вторично.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from django.conf import settings
from django.core.mail import EmailMessage, mailers
from django.utils.module_loading import import_string

if TYPE_CHECKING:
    from memiro.inquiries.models import Inquiry, InquiryItem

logger = logging.getLogger(__name__)


class InquiryNotifier(Protocol):
    """Транспорт уведомления о заявке."""

    def send(self, inquiry: Inquiry) -> None: ...


def wish_lines(wish: str) -> list[str]:
    """Пожелание позиции — своими строками под своим зеркалом.

    Переносы покупателя сохраняются, но каждая строка получает тот же
    отступ, что и расчёт: иначе вторая строка пожелания встала бы
    вровень с позициями и прочиталась бы как ещё одно зеркало.

    Пустые строки остаются пустыми, а не выбрасываются: абзацы ставил
    покупатель, и править его текст письмо не вправе. Отступа им не
    достаётся — строка из одних пробелов читается хуже пустой.
    """
    said = wish.splitlines()
    if not any(line.strip() for line in said):
        return []
    return [
        f"  Пожелание: {said[0]}",
        *(f"  {line}" if line.strip() else "" for line in said[1:]),
    ]


def item_lines(item: InquiryItem) -> list[str]:
    """Позиция в письме: зеркало, его расчёт и его пожелание.

    Конфигурация печатается у своего зеркала, а не над составом: у
    зеркала в ванную и у зеркала в прихожую разные размеры, и
    сложенные в одну строку они заставили бы менеджера разбирать,
    что к чему относится (ADR-0009).

    Позиции без конфигурации остаётся «цена от»: калькулятор есть не
    у всякого товара, и настраивать покупателю там было нечего.

    Размер за пределом производства цены не получает: это личное
    пожелание, и цену называет менеджер — но увидеть это он должен
    в заявке, а не вывести из молчания.
    """
    # Цену словами называет сама позиция: письмо и админка читают
    # заявку одинаково, а «не рассчитана» пишется в одном месте
    lines = [f"— {item.product_name}, {item.product_price_label()}"]
    if item.configuration:
        # То, что покупатель настроил на карточке, — менеджер звонит
        # со знанием дела, а не переспрашивает размеры
        lines.append(f"  Расчёт: {item.configuration}")
        lines.append(f"  Показанная цена: {item.calculated_price_label()}")
    # Пожелание печатается и там, где расчёта не было вовсе: у товара
    # без калькулятора настраивать было нечего, а сказать словами
    # покупателю есть что (тикет 15)
    return lines + wish_lines(item.wish)


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
        # «Состав», а не «Товары»: строк столько, сколько позиций,
        # и одно зеркало двумя размерами — две из них (CONTEXT.md,
        # «Позиция заявки»)
        lines.append("Состав заявки:")
        for item in items:
            lines += item_lines(item)
    if inquiry.comment:
        lines.append(f"Комментарий: {inquiry.comment}")
    return "\n".join(lines)


def inquiry_subject(inquiry: Inquiry) -> str:
    """Тема письма: номер и источник.

    По ней менеджер находит заявку в журнале, не открывая письма, и
    отличает две заявки одного человека друг от друга.
    """
    return f"Заявка №{inquiry.pk} — {inquiry.get_source_display()}"


class EmailNotifier:
    """Письмо менеджеру; без адреса — только запись в лог.

    Реквизиты ящика живут в окружении (`MAILERS` собирается из него в
    настройках, адрес менеджера — `INQUIRY_MANAGER_EMAIL`), а не в коде:
    пароль приложения — секрет, и в репозиторий ему нельзя.
    """

    def send(self, inquiry: Inquiry) -> None:
        manager = settings.INQUIRY_MANAGER_EMAIL
        if not manager:
            logger.warning(
                "Адрес менеджера не задан, заявка №%s без уведомления",
                inquiry.pk,
            )
            return
        letter = EmailMessage(
            subject=inquiry_subject(inquiry),
            body=inquiry_message(inquiry),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[manager],
        )
        # Отправка через `mailers`, а не через `letter.send()`: второй
        # ходит устаревшим путём, которого в Django 7.0 не будет.
        # Сбой не глушится — его ловит notify() и пишет в лог с
        # трассировкой, а молчаливая отправка «в никуда» оставила бы
        # менеджера без заявки и без следа о том, почему
        mailers.default.send_messages([letter])


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
