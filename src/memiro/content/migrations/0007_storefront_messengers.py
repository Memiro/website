"""Мессенджеры на витрине: Telegram и WhatsApp уходят, MAX встаёт (тикет 08).

Контакты студии — телефон, почта и MAX (решение владельца). Ссылку
владелец пришлёт позже, но иконка ставится сразу, с заглушкой: сайт
не запущен, ломать нечего, а забыть про иконку легче, чем про пустое
место. Заглушка — корень `max.ru`, а не выдуманное имя профиля:
придуманный адрес привёл бы на чужую страницу, а корень просто никуда
не ведёт. Владелец меняет её в админке, без выкатки.

Транспорт уведомления менеджеру (`TelegramNotifier`) тут ни при чём —
это тикет 19. Иконка на витрине и труба, по которой едет заявка, —
разные вещи.
"""

from typing import TYPE_CHECKING

from django.db import migrations, models

if TYPE_CHECKING:
    from django.apps.registry import Apps
    from django.db.backends.base.schema import BaseDatabaseSchemaEditor

MAX_PLACEHOLDER = "https://max.ru/"


def fill_placeholder(
    apps: Apps,
    schema_editor: BaseDatabaseSchemaEditor | None,
) -> None:
    apps.get_model("content", "SiteContacts").objects.update(
        max_link=MAX_PLACEHOLDER
    )


def clear_placeholder(
    apps: Apps,
    schema_editor: BaseDatabaseSchemaEditor | None,
) -> None:
    apps.get_model("content", "SiteContacts").objects.update(max_link="")


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0006_alter_sitecontacts_avito"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="sitecontacts",
            name="telegram",
        ),
        migrations.RemoveField(
            model_name="sitecontacts",
            name="whatsapp",
        ),
        migrations.AddField(
            model_name="sitecontacts",
            name="max_link",
            field=models.URLField(
                blank=True,
                help_text="Ссылка на профиль студии в MAX. Заглушка "
                "«https://max.ru/» поисковику не уходит: витрина иконку "
                "рисует, а разметка профиля не называет, пока не стоит "
                "настоящий адрес.",
                verbose_name="MAX",
            ),
        ),
        migrations.RunPython(fill_placeholder, clear_placeholder),
    ]
