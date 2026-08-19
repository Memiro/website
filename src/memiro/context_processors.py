"""Контекст, доступный каждому шаблону витрины."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest

# Контакты студии — единственный источник для шапки, меню и футера
CONTACTS = {
    "phone": "+79812304050",
    "phone_display": "+7 981 230-40-50",
    "email": "memiro.ru@yandex.ru",
}


# Сигнатуру с request диктует контракт context processor'а Django
def contacts(request: HttpRequest) -> dict[str, dict[str, str]]:  # noqa: ARG001
    return {"contacts": CONTACTS}
