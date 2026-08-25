"""Личное пожелание получает место у позиции заявки (тикет 15).

Данных не двигает: у принятых заявок пожеланий не было вовсе, и
выдумывать их не из чего. Комментарий заявки остаётся на месте —
свободной форме с главной, где товара нет, писать больше некуда.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inquiries", "0005_configuration_per_item"),
    ]

    operations = [
        migrations.AddField(
            model_name="inquiryitem",
            name="wish",
            field=models.CharField(
                blank=True, max_length=500, verbose_name="личное пожелание"
            ),
        ),
    ]
