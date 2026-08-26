"""Заявка уходит менеджеру письмом (тикет 19).

Про состав письма спрашивает `test_inquiries.py` — там живёт
`inquiry_message()`. Здесь спрашивают про транспорт: кому уходит, с
какой темой и что бывает, когда почта молчит.
"""

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from django.test import Client
from pytest_django.fixtures import Settings

from memiro.inquiries.models import Inquiry
from memiro.inquiries.notifications import inquiry_message
from tests.inquiries import (
    calculable,
    item,
    post_calculated,
    post_inquiry,
)

if TYPE_CHECKING:
    from types import SimpleNamespace

# Фикстура приезжает импортом, но pytest узнаёт её только по имени
# в модуле — линтеру это видится неиспользованным именем
__all__ = ["calculable"]

EMAIL = "memiro.inquiries.notifications.EmailNotifier"
MANAGER = "manager@example.com"
SENDER = "robot@memiro.ru"

# Одно и то же зеркало двумя размерами — две строки состава
MIRRORS_IN_THE_CART = 2
# Размер, которого производство не берёт: цену называет менеджер
ABSURD_WIDTH_MM = 900_000


@pytest.fixture
def mailing(settings: Settings) -> None:
    """Прод-транспорт с адресами: письма собирает locmem-бэкенд."""
    settings.INQUIRY_NOTIFIER = EMAIL
    settings.INQUIRY_MANAGER_EMAIL = MANAGER
    settings.DEFAULT_FROM_EMAIL = SENDER


@pytest.mark.django_db
def test_the_inquiry_reaches_the_manager_by_mail(
    client: Client, calculable: SimpleNamespace, mailing: None
) -> None:
    """Одна заявка — одно письмо менеджеру, и текст в нём тот же."""
    post_calculated(client, calculable)

    assert len(mail.outbox) == 1
    letter = mail.outbox[0]
    assert letter.to == [MANAGER]
    assert letter.from_email == SENDER
    assert letter.body == inquiry_message(Inquiry.objects.get())


@pytest.mark.django_db
def test_the_subject_finds_the_inquiry(
    client: Client, calculable: SimpleNamespace, mailing: None
) -> None:
    """По теме письма заявка находится в журнале: номер и источник."""
    post_calculated(client, calculable)

    inquiry = Inquiry.objects.get()
    assert mail.outbox[0].subject == f"Заявка №{inquiry.pk} — корзина"


@pytest.mark.django_db
def test_two_mirrors_arrive_with_their_own_calculations(
    client: Client, calculable: SimpleNamespace, mailing: None
) -> None:
    """Каждое зеркало письмо печатает со своим расчётом и пожеланием.

    Зеркало в ванную и зеркало в прихожую — разные размеры и разные
    цены (ADR-0009): сложи их письмо в одну строку, и менеджер
    изготовит не то.
    """
    post_inquiry(
        client,
        items=[
            item(
                calculable.product,
                width_mm=800,
                height_mm=600,
                values=[calculable.silver.pk],
                wish="В прихожую",
            ),
            item(
                calculable.product,
                width_mm=1200,
                height_mm=700,
                values=[calculable.silver.pk, calculable.heating.pk],
                wish="В ванную, с подогревом",
            ),
        ],
    )

    body = mail.outbox[0].body
    assert body.count("— Halo Moon") == MIRRORS_IN_THE_CART
    assert "Расчёт: 800 × 600 мм; Тип полотна: Серебро" in body
    assert (
        "Расчёт: 1200 × 700 мм; Тип полотна: Серебро; Подогрев: Есть" in body
    )
    assert "Пожелание: В прихожую" in body
    assert "Пожелание: В ванную, с подогревом" in body


@pytest.mark.django_db
def test_a_price_that_was_never_named_says_so(
    client: Client, calculable: SimpleNamespace, mailing: None
) -> None:
    """Размер за пределом производства: цену называет менеджер.

    Менеджеру важно прочитать это словами, а не гадать по пустому
    месту.
    """
    post_calculated(client, calculable, width_mm=ABSURD_WIDTH_MM)

    body = mail.outbox[0].body
    assert "Показанная цена: не рассчитана" in body
    assert "None" not in body


@pytest.mark.django_db
def test_without_a_manager_address_the_inquiry_still_lands(
    client: Client,
    calculable: SimpleNamespace,
    mailing: None,
    settings: Settings,
) -> None:
    """Адрес не заведён — заявка в журнале, письма нет, ошибки нет."""
    settings.INQUIRY_MANAGER_EMAIL = ""

    response = post_calculated(client, calculable)

    assert response.status_code == HTTPStatus.CREATED
    assert Inquiry.objects.count() == 1
    assert not mail.outbox


@pytest.mark.django_db
def test_a_silent_smtp_does_not_cost_the_lead(
    client: Client,
    calculable: SimpleNamespace,
    mailing: None,
    settings: Settings,
) -> None:
    """Чужой SMTP упал — заявка всё равно принята и записана.

    Падение здесь глубже, чем в `test_inquiry_survives_broken_notifier`:
    там ломается сам транспорт, здесь — почтовый бэкенд под ним. Это и
    проверяется: `EmailNotifier` не глушит ошибку отправки, и поймать
    её должен `notify()`.
    """
    settings.MAILERS = {
        "default": {"BACKEND": "tests.notifiers.FailingEmailBackend"}
    }

    response = post_calculated(client, calculable)

    assert response.status_code == HTTPStatus.CREATED
    assert Inquiry.objects.count() == 1
