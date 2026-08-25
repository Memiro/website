"""Конфигурация и посчитанная цена переезжают на позицию (ADR-0009).

Данные принятых заявок не теряются: снимок заявки достаётся её
единственной позиции — там, где позиция одна и есть кому его отдать.
Заявке из нескольких позиций снимок раздать некому: какое из зеркал
покупатель считал, знает только он, а угаданная конфигурация хуже
отсутствующей — менеджер изготовил бы не то. Заявке свободной формой
снимка и не полагалось.
"""

from typing import TYPE_CHECKING, Any

from django.db import migrations, models

if TYPE_CHECKING:
    from django.apps.registry import Apps
    from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def move_to_the_only_item(
    apps: "Apps",
    schema_editor: "BaseDatabaseSchemaEditor",  # noqa: ARG001
) -> None:
    """Снимок заявки — её единственной позиции."""
    # Any, а не модель: у нынешней `Inquiry` этих полей уже нет, и
    # статический анализ прав — их видит только историческая модель
    inquiries: Any = apps.get_model("inquiries", "Inquiry")
    for inquiry in inquiries.objects.exclude(
        configuration=""
    ).prefetch_related("items"):
        items = list(inquiry.items.all())
        if len(items) != 1:
            continue
        item = items[0]
        item.configuration = inquiry.configuration
        item.calculated_price = inquiry.calculated_price
        item.save(update_fields=("configuration", "calculated_price"))


def move_back_to_the_inquiry(
    apps: "Apps",
    schema_editor: "BaseDatabaseSchemaEditor",  # noqa: ARG001
) -> None:
    """Откат: снимок позиции возвращается заявке.

    Заявке из нескольких настроенных позиций вернуть можно только
    одну — вторая правда, ради ухода от которой поля и переезжали.
    Берётся первая: откат обратим по данным ровно настолько, насколько
    старая модель их вмещала.
    """
    inquiries: Any = apps.get_model("inquiries", "Inquiry")
    for inquiry in inquiries.objects.prefetch_related("items"):
        configured = [
            item for item in inquiry.items.all() if item.configuration
        ]
        if not configured:
            continue
        inquiry.configuration = configured[0].configuration
        inquiry.calculated_price = configured[0].calculated_price
        inquiry.save(update_fields=("configuration", "calculated_price"))


class Migration(migrations.Migration):
    dependencies = [
        ("inquiries", "0004_inquiry_calculated_price_inquiry_configuration"),
    ]

    operations = [
        migrations.AddField(
            model_name="inquiryitem",
            name="configuration",
            field=models.TextField(
                blank=True, verbose_name="конфигурация расчёта"
            ),
        ),
        migrations.AddField(
            model_name="inquiryitem",
            name="calculated_price",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="посчитанная цена, ₽"
            ),
        ),
        migrations.RunPython(move_to_the_only_item, move_back_to_the_inquiry),
        migrations.RemoveField(model_name="inquiry", name="configuration"),
        migrations.RemoveField(model_name="inquiry", name="calculated_price"),
    ]
