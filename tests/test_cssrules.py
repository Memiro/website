"""Разбор таблицы стилей — на нём держатся структурные тесты вёрстки.

Разбор самодельный, и ошибиться он может молча: тест на цену спрашивает,
объявлено ли свойство *безусловно*, и неверно посчитанная вложенность
превращается не в падение, а в зелёный тест на сломанной вёрстке. Поэтому
проверяется сам разбор, а не только его выводы.
"""

from __future__ import annotations

import pytest

from tests.cssrules import (
    Rule,
    StylesheetError,
    classes,
    rules,
    stylesheet,
)

# Единственное правило обеих коротких таблиц ниже
PRICE_RULE = Rule(".price", " white-space: nowrap; ", conditional=False)

FONT_FACE = """
@font-face {
  font-family: "Golos Text";
  src: url("../fonts/golos.woff2") format("woff2");
}
.price { white-space: nowrap; }
"""

MEDIA = """
.price { font-size: 24px; }
@media (max-width: 640px) {
  .price { white-space: nowrap; }
}
.name { font-size: 16px; }
"""


def test_at_rule_without_nested_rules_leaves_nothing_behind() -> None:
    """`@font-face` не приклеивается к следующему селектору.

    Внутри него нет вложенных правил, и объявления, если их не сбросить,
    доедут до ближайшей открывающей скобки и станут частью её селектора.
    """
    assert rules(FONT_FACE) == [PRICE_RULE]


def test_media_marks_nested_rules_conditional() -> None:
    assert [(rule.selector, rule.conditional) for rule in rules(MEDIA)] == [
        (".price", False),
        (".price", True),
        (".name", False),
    ]


def test_at_rule_with_semicolon_does_not_open_a_block() -> None:
    """`@import` заканчивается точкой с запятой, а не блоком.

    Прими его за блочный — и `depth` больше никогда не вернётся к нулю:
    все правила файла станут условными, а тест на цену — зелёным.
    """
    css = '@import url("reset.css");\n.price { white-space: nowrap; }'

    assert rules(css) == [PRICE_RULE]


def test_unbalanced_braces_are_loud() -> None:
    """Незакрытое правило — испорченный файл, а не пустой разбор."""
    with pytest.raises(StylesheetError, match="незакрытое"):
        rules(".price { white-space: nowrap;")


def test_site_css_parses_into_selectors_only() -> None:
    """Ни один селектор живой таблицы не содержит объявлений."""
    smuggled = [
        rule.selector for rule in rules(stylesheet()) if ";" in rule.selector
    ]

    assert not smuggled, "В селектор попало объявление: " + "; ".join(
        selector[:60] for selector in smuggled
    )


def test_classes_takes_the_whole_selector_list() -> None:
    assert classes(".grid-4, .grid-3 > .tile") == {"grid-4", "grid-3", "tile"}
