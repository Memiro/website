"""Акция под товары, у которых флаг «акция» уже стоял.

До тикета 08 блок специальных цен на главной жил в шаблоне и появлялся
от одного флага товара. Теперь его заголовок берётся из акции — без этой
записи витрина с уже отмеченными товарами молча потеряла бы блок.
"""

from typing import TYPE_CHECKING

from django.db import migrations

if TYPE_CHECKING:
    from django.apps.registry import Apps
    from django.db.backends.base.schema import BaseDatabaseSchemaEditor

# Заголовок и примечание — ровно те, что стояли в шаблоне до тикета 08
LEGACY_TITLE = "Специальные цены"
LEGACY_TEXT = "Подробности акции уточняйте у нашего менеджера"


def create_promo_for_flagged_products(
    apps: Apps,
    schema_editor: BaseDatabaseSchemaEditor | None,
) -> None:
    promo_model = apps.get_model("content", "Promo")
    product_model = apps.get_model("catalog", "Product")
    if promo_model.objects.exists():
        return
    if not product_model.objects.filter(
        is_promo=True, is_published=True
    ).exists():
        return
    promo_model.objects.create(
        title=LEGACY_TITLE,
        text=LEGACY_TEXT,
        is_published=True,
    )


def drop_promo(
    apps: Apps,
    schema_editor: BaseDatabaseSchemaEditor | None,
) -> None:
    apps.get_model("content", "Promo").objects.filter(
        title=LEGACY_TITLE
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0002_faqentry_promo_review_alter_work_is_published"),
        ("catalog", "0002_product_created_at"),
    ]

    operations = [
        migrations.RunPython(create_promo_for_flagged_products, drop_promo),
    ]
