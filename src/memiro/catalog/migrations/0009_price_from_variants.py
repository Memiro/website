"""Цена товара впредь считается из вариантов — пересчитать разом.

После переноса каталога 48 товаров стоят с заглушкой 1 ₽: цену
владелец в старом сайте не вёл, а поле было обязательным. Теперь
поле необязательно, и правда о цене одна — самый дешёвый
предпосчитанный вариант товара. У кого вариантов нет, у того нет
и цены: пустое поле честнее единицы (ADR-0007, тикет 18).
"""

from typing import Any

from django.db import migrations
from django.db.models import Min, OuterRef, Subquery


def price_from_variants(apps: Any, schema_editor: Any) -> None:
    """Тот же подзапрос, что и `repricing.settle_prices()`.

    Позвать её нельзя: миграция считает по историческим моделям и
    должна пережить любую будущую правку кода — потому выражение
    здесь повторено, а не заимствовано.
    """
    Product = apps.get_model("catalog", "Product")
    ProductVariant = apps.get_model("catalog", "ProductVariant")
    Product.objects.update(
        price=Subquery(
            ProductVariant.objects.filter(product_id=OuterRef("pk"))
            .values("product_id")
            .annotate(cheapest=Min("price"))
            .values("cheapest")
        )
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0008_alter_product_price"),
    ]

    operations = [
        # Назад не разворачивается: старых цен, введённых руками,
        # уже нет — восстанавливать нечего
        migrations.RunPython(price_from_variants, migrations.RunPython.noop),
    ]
