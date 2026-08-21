"""Русская типографика витрины: цены и склонения.

Модуль обычный, не templatetags: подписи собираются и в шаблонах, и в
коде (чипсы фильтров), а одно число на странице должно выглядеть
одинаково независимо от того, кто его напечатал.
"""

from __future__ import annotations

# Узкий неразрывный пробел — разделитель тысяч в русской типографике
THIN_SPACE = " "  # noqa: RUF001

# Числа на -надцать склоняются как «много»: 11 товаров, 12 товаров
TEEN_FLOOR, TEEN_CEIL = 11, 14


def rub(value: int) -> str:
    """Цена с разбивкой тысяч: 11 795."""
    return f"{value:,}".replace(",", THIN_SPACE)


def ru_plural(value: int, forms: str) -> str:
    """Русское склонение: ru_plural(3, "товар,товара,товаров")."""
    one, few, many = forms.split(",")
    tail, teens = value % 10, value % 100
    if TEEN_FLOOR <= teens <= TEEN_CEIL:
        return many
    if tail == 1:
        return one
    if tail in {2, 3, 4}:
        return few
    return many
