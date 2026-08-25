"""Цена печатается одной строкой — символ рубля не уезжает вниз.

Ценник собран из трёх кусков, разделённых обычными пробелами: «от»,
число и «₽». Разделитель тысяч внутри числа — узкий неразрывный пробел,
так что само число не рвётся, а вот перед «₽» и после «от» строка
ломается свободно. На узкой плитке каталога так и вышло: рубль уезжал
на вторую строку. Лечится это `white-space: nowrap` у того класса,
который печатает цену.

Классы ниже — все места витрины, где стоит цена. Появится четвёртое —
дописывается сюда, и тест сразу скажет, забыли ли про перенос.
Требование безусловное: объявление из `@media` не считается, иначе
запрет переноса, заведённый для широкого экрана, закрыл бы собой
узкий — то есть ровно тот, где цена и ломалась.
"""

from __future__ import annotations

import re

from tests.cssrules import classes, rules, stylesheet

# Все места витрины, где стоит цена: плитка каталога (`.price`),
# «от X ₽» в шапке карточки (`.price-now`), итог калькулятора
# (`.calc-total`, собирается в `static/js/product.js`), строка корзины
# и таблица вариантов
PRICE_CLASSES = frozenset(
    {"price", "price-now", "calc-total", "cart-price", "variant-price"},
)

NOWRAP = re.compile(r"white-space\s*:\s*nowrap")


def test_every_price_class_forbids_wrapping() -> None:
    protected = {
        name
        for rule in rules(stylesheet())
        if not rule.conditional and NOWRAP.search(rule.body)
        for name in classes(rule.selector)
    }

    assert not PRICE_CLASSES - protected, (
        "Цена без безусловного `white-space: nowrap` — рубль уедет на "
        "вторую строку: " + ", ".join(sorted(PRICE_CLASSES - protected))
    )
