"""Контекст, доступный каждому шаблону витрины."""

from typing import TYPE_CHECKING

from memiro.inquiries import limits

if TYPE_CHECKING:
    from django.http import HttpRequest

# Контакты студии — единственный источник для шапки, меню, футера
# и страницы «Контакты»
CITY = "Санкт-Петербург"
STREET = "ул. Тележная, 37"

CONTACTS = {
    "phone": "+79812304050",
    "phone_display": "+7 981 230-40-50",
    "email": "memiro.ru@yandex.ru",
    # Город и улица — отдельно: разметка LocalBusiness (тикет 09) просит
    # их порознь, а витрине нужна одна строка
    "city": CITY,
    "street": STREET,
    "address": f"{CITY}, {STREET}",
    "hours": "Ежедневно, по предварительной записи",
    # Часы для разметки LocalBusiness: витрина говорит человеку
    # «по предварительной записи», а поисковику нужны границы. Точных
    # часов владелец пока не дал — до тех пор разметка о часах молчит,
    # выдумывать их нельзя. Заполните оба поля, и расписание появится.
    "opens": "",
    "closes": "",
    "telegram": "https://t.me/memiro_shop",
    "whatsapp": "https://wa.me/79812304050",
    "vk": "https://vk.com/memirospb",
    # Витрина продавца на Avito — источник отзывов студии
    "avito": (
        "https://www.avito.ru/brands/i213339688/all"
        "?sellerId=390e2bdb64de6df7a4c7747af56411ba"
    ),
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


def inquiry_limits(request: HttpRequest) -> dict[str, dict[str, int]]:  # noqa: ARG001
    """Границы заявки — в шаблон и оттуда в `shop.js` (см. limits.py)."""
    return {
        "inquiry_limits": {
            "max_items": limits.MAX_ITEMS,
            "min_phone_digits": limits.MIN_PHONE_DIGITS,
        },
    }
