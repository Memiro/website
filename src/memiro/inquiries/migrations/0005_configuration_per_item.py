"""Конфигурация и посчитанная цена переезжают на позицию (ADR-0009).

Данные принятых заявок не теряются. Снимок достаётся единственной
позиции заявки — там, где позиция одна и есть кому его отдать.

Отдать его некому в двух случаях, и оба реальны: заявка о нескольких
зеркалах (какое из них покупатель считал, знает только он) и заявка,
принятая вовсе без позиций (так до тикета 07 приходил расчёт с
карточки — старый разбор писал в снимок габариты, даже не найдя
единственного товара). Угаданная позиция была бы хуже отсутствующей:
менеджер изготовил бы не то. Но и стереть снимок нельзя — «заявки без
позиций не теряют ничего» (тикет 14), а прочитать заявку менеджер
должен и через год.

Поэтому такой снимок дописывается в комментарий заявки: там уже живёт
всё, что покупатель сказал о заявке словами, и там его никто не примет
за конфигурацию зеркала. Заявке свободной формой снимка не полагалось
вовсе — её этот путь не касается.
"""

from typing import TYPE_CHECKING, Any

from django.db import migrations, models

if TYPE_CHECKING:
    from django.apps.registry import Apps
    from django.db.backends.base.schema import BaseDatabaseSchemaEditor


# Как снимок подписан в комментарии, когда позиции ему не нашлось.
# Подпись, а не голая строка: через год менеджер должен понять,
# откуда в комментарии взялись миллиметры
KEPT_IN_COMMENT = "Расчёт из заявки (до переезда на позиции):"


def move_to_the_only_item(
    apps: "Apps",
    schema_editor: "BaseDatabaseSchemaEditor",  # noqa: ARG001
) -> None:
    """Снимок заявки — её единственной позиции или её комментарию."""
    # Any, а не модель: у нынешней `Inquiry` этих полей уже нет, и
    # статический анализ прав — их видит только историческая модель
    inquiries: Any = apps.get_model("inquiries", "Inquiry")
    for inquiry in inquiries.objects.exclude(
        configuration=""
    ).prefetch_related("items"):
        items = list(inquiry.items.all())
        if len(items) == 1:
            item = items[0]
            item.configuration = inquiry.configuration
            item.calculated_price = inquiry.calculated_price
            item.save(update_fields=("configuration", "calculated_price"))
            continue
        inquiry.comment = _with_snapshot(inquiry)
        inquiry.save(update_fields=("comment",))


def _with_snapshot(inquiry: Any) -> str:
    """Комментарий заявки, дописанный её снимком.

    Цена печатается рядом с конфигурацией, а не отдельной строкой:
    порознь они однажды разъедутся при копировании. Цены может не
    быть — и тогда об этом сказано словами, а не пропуском.
    """
    price = (
        f"{inquiry.calculated_price} ₽"
        if inquiry.calculated_price is not None
        else "цена не рассчитана"
    )
    kept = f"{KEPT_IN_COMMENT} {inquiry.configuration} — {price}"
    return f"{inquiry.comment}\n\n{kept}" if inquiry.comment else kept


def move_back_to_the_inquiry(
    apps: "Apps",
    schema_editor: "BaseDatabaseSchemaEditor",  # noqa: ARG001
) -> None:
    """Откат: снимок позиции возвращается заявке.

    Заявке из нескольких настроенных позиций вернуть можно только
    одну — вторая правда, ради ухода от которой поля и переезжали.
    Берётся первая по `pk`, как их и упорядочивает `InquiryItem`:
    откат обратим по данным ровно настолько, насколько старая модель
    их вмещала.

    Дописанное в комментарий назад не разбирается: комментарий —
    свободный текст покупателя, и вырезать из него строку по подписи
    значило бы однажды вырезать не ту.
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
        # Подпись едет тем же тикетом: «товар заявки» звал позицию
        # товаром, а словарь эти термины развёл (CONTEXT.md, «Товар»,
        # «Позиция заявки»). Схемы не касается — только админки
        migrations.AlterModelOptions(
            name="inquiryitem",
            options={
                "ordering": ("pk",),
                "verbose_name": "позиция заявки",
                "verbose_name_plural": "состав заявки",
            },
        ),
        migrations.RemoveField(model_name="inquiry", name="configuration"),
        migrations.RemoveField(model_name="inquiry", name="calculated_price"),
    ]
