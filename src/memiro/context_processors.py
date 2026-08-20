"""Контекст, доступный каждому шаблону витрины."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest

# Контакты студии — единственный источник для шапки, меню, футера
# и страницы «Контакты»
CONTACTS = {
    "phone": "+79812304050",
    "phone_display": "+7 981 230-40-50",
    "email": "memiro.ru@yandex.ru",
    "address": "Санкт-Петербург, ул. Тележная, 37",
    "hours": "Ежедневно, по предварительной записи",
    "telegram": "https://t.me/memiro_shop",
    "whatsapp": "https://wa.me/79812304050",
    "vk": "https://vk.com/memirospb",
    # Карта шоурума — конструктор Яндекс.Карт (перенесена со старого сайта)
    "map_embed": (
        "https://yandex.ru/map-widget/v1/?um=constructor%3A"
        "0d49dffecadc7ce7a218e08a0b62b35502b15e05faa72ecea01c3be9dea4a3f1"
        "&source=constructor"
    ),
}


# Сигнатуру с request диктует контракт context processor'а Django
def contacts(request: HttpRequest) -> dict[str, dict[str, str]]:  # noqa: ARG001
    return {"contacts": CONTACTS}
