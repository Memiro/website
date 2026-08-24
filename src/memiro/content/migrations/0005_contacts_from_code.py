"""Нынешние контакты из кода — в первую строку админки.

До тикета 01 всё это лежало словарём `CONTACTS` в
`memiro/context_processors.py`. Значения здесь — ровно те, что стояли
в словаре, кроме адреса: владелец переехал на Александра Матросова
(пункт 3 списка правок). Сайт после миграции выглядит как до неё.
"""

from typing import TYPE_CHECKING

from django.db import migrations

if TYPE_CHECKING:
    from django.apps.registry import Apps
    from django.db.backends.base.schema import BaseDatabaseSchemaEditor

CONTACTS = {
    "city": "Санкт-Петербург",
    "street": "Александра Матросова, 4к2ж",
    "phone": "+79812304050",
    "phone_display": "+7 981 230-40-50",
    "email": "memiro.ru@yandex.ru",
    "hours": "Ежедневно, по предварительной записи",
    # Точных часов владелец не давал — до тех пор разметка о часах
    # молчит, выдумывать их нельзя
    "opens": None,
    "closes": None,
    "telegram": "https://t.me/memiro_shop",
    "whatsapp": "https://wa.me/79812304050",
    "vk": "https://vk.com/memirospb",
    "avito": (
        "https://www.avito.ru/brands/i213339688/all"
        "?sellerId=390e2bdb64de6df7a4c7747af56411ba"
    ),
    "map_embed": (
        "https://yandex.ru/map-widget/v1/?um=constructor%3A"
        "0d49dffecadc7ce7a218e08a0b62b35502b15e05faa72ecea01c3be9dea4a3f1"
        "&source=constructor"
    ),
}


def fill_contacts(
    apps: Apps,
    schema_editor: BaseDatabaseSchemaEditor | None,
) -> None:
    contacts_model = apps.get_model("content", "SiteContacts")
    if contacts_model.objects.exists():
        return
    contacts_model.objects.create(pk=1, **CONTACTS)


def drop_contacts(
    apps: Apps,
    schema_editor: BaseDatabaseSchemaEditor | None,
) -> None:
    apps.get_model("content", "SiteContacts").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0004_sitecontacts"),
    ]

    operations = [
        migrations.RunPython(fill_contacts, drop_contacts),
    ]
