"""Подсказка у ссылки на Avito перестаёт обещать блок отзывов.

Она звала поле «источником отзывов» и ссылкой «Смотреть все» — а блок,
из которого та ссылка вела, снят с главной (тикет 06 набора
`owner-revision`). Для базы правка пустая: меняется только текст,
который владелец читает под полем.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0005_contacts_from_code"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sitecontacts",
            name="avito",
            field=models.URLField(
                blank=True,
                help_text="Витрина студии на Avito. Сейчас ссылку видят только поисковики: блок отзывов, из которого вела «Смотреть все», снят.",
                verbose_name="витрина на Avito",
            ),
        ),
    ]
