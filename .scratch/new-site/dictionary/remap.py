"""Справочник зеркал под набор владельца и переразметка товаров (тикет 22).

Разовая операция, а не часть продукта: скрипт живёт здесь, в кодовую
базу и зависимости проекта не попадает. Запуск из корня репозитория:

    uv run python .scratch/new-site/dictionary/remap.py

Что делает прогон:

* приводит справочник категории «Зеркала» к набору владельца — тип
  полотна, форма, рама, цвет рамы, подсветка, температура свечения,
  кнопка, крепление, подогрев, вырез;
* переносит разметку 88 зеркал там, где перенос однозначен;
* стирает разметку там, где старое поле нового ответа не знает, и
  собирает такие товары в отчёт — их доразмечает владелец.

Тарифы прогон не ставит: ставки — цифры владельца, и выдуманные
однажды назвали бы покупателю неверную цену. Значения заводятся
бесплатными, единицу расхода и ставку владелец проставляет сам
(рекомендованные единицы — в README рядом).

Повторный прогон ничего не портит: справочник доводится до того же
набора, а разметка, которую владелец успел проставить руками, остаётся
на месте — переносится только то, что ещё лежит в старых атрибутах.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import django
from django.apps import apps

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

if not apps.ready:
    sys.path.insert(0, str(REPO / "src"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memiro.settings")
    django.setup()

from django.db import transaction  # noqa: E402

from memiro.catalog import calculator, tariffs  # noqa: E402
from memiro.catalog.models import (  # noqa: E402
    Attribute,
    AttributeValue,
    Category,
    Landing,
    LandingCondition,
    ProductAttribute,
    exhausts_dictionary,
)

CATEGORY_SLUG = "zerkala"

# Отчёт о том, что осталось владельцу: список слагов по каждому пробелу
DEFAULT_REPORT = HERE / "owner-todo.md"


@dataclass(frozen=True)
class ValueSpec:
    """Строка справочника: подпись и что она значит для зависимостей."""

    value: str
    marks_absence: bool = False


@dataclass(frozen=True)
class AttributeSpec:
    """Атрибут набора владельца — таблица из тикета 22, строка за строкой.

    `parents` — слаги атрибутов, без которых этого не бывает: кнопки
    не бывает без подсветки или подогрева, температуры свечения — без
    подсветки, цвета рамы — без рамы.
    """

    slug: str
    name: str
    values: tuple[ValueSpec, ...] = ()
    kind: str = Attribute.Kind.CHOICE
    is_customer_editable: bool = False
    is_filterable: bool = True
    parents: tuple[str, ...] = ()


def _absent(value: str) -> ValueSpec:
    return ValueSpec(value, marks_absence=True)


# Набор владельца. Порядок строк — порядок в админке и в характеристиках
OWNER_SET = (
    AttributeSpec(
        "tip-polotna",
        "Тип полотна",
        (
            ValueSpec("Серебро"),
            ValueSpec("Осветлённое"),
            ValueSpec("Бронза"),
            ValueSpec("Графит"),
        ),
        is_customer_editable=True,
        # Любое зеркало делают из любого полотна: группа фильтра
        # спрятала бы товары, которые на самом деле подходят
        is_filterable=False,
    ),
    AttributeSpec(
        "form",
        "Форма",
        (
            ValueSpec("Прямоугольное"),
            ValueSpec("Круглое"),
            ValueSpec("Фигурное"),
        ),
    ),
    AttributeSpec(
        "frame",
        "Рама",
        (ValueSpec("Алюминий"), ValueSpec("Багет"), _absent("Без рамы")),
    ),
    AttributeSpec(
        "frame-color",
        "Цвет рамы",
        (
            ValueSpec("Чёрный"),
            ValueSpec("Белый"),
            ValueSpec("Золото"),
            ValueSpec("Серебро"),
            ValueSpec("Бронза"),
            ValueSpec("Голубой"),
            ValueSpec("Другое"),
        ),
        parents=("frame",),
    ),
    AttributeSpec(
        "backlight",
        "Подсветка",
        (
            ValueSpec("Контурная"),
            ValueSpec("Фронтальная"),
            ValueSpec("Комбинированная"),
            _absent("Без подсветки"),
        ),
    ),
    AttributeSpec(
        "temperature",
        "Температура свечения",
        (
            ValueSpec("Холодная"),
            ValueSpec("Тёплая"),
            ValueSpec("Нейтральная"),
            ValueSpec("3 в 1"),
        ),
        parents=("backlight",),
    ),
    AttributeSpec(
        "button",
        "Кнопка",
        (
            ValueSpec("Механическая"),
            ValueSpec("Сенсорная"),
            ValueSpec("Датчик на взмах"),
            _absent("Без кнопки"),
        ),
        parents=("backlight", "heating"),
    ),
    AttributeSpec(
        "mount",
        "Крепление",
        (
            ValueSpec("С креплением"),
            ValueSpec("На ножке"),
            _absent("Без крепления"),
        ),
        is_customer_editable=True,
    ),
    AttributeSpec(
        "heating",
        "Подогрев",
        (ValueSpec("С подогревом"), _absent("Без подогрева")),
        is_customer_editable=True,
    ),
    AttributeSpec(
        "cutout",
        "Вырез",
        # Одна строка справочника — тариф за штуку; сколько их у
        # изделия, говорит число у товара
        (ValueSpec("Вырез"),),
        kind=Attribute.Kind.NUMBER,
        is_filterable=False,
    ),
)

# Однозначные переносы: (слаг старого атрибута, значение) →
# (слаг нового атрибута, значение). Всё, чего здесь нет, — пробел,
# который заполняет владелец: старое «С подсветкой» не говорит,
# контурная лента или фронтальная, а от этого зависит, считать по
# периметру или по площади
CARRIED_OVER = {
    ("frame-material", "Алюминий"): ("frame", "Алюминий"),
    ("location", "Напольное"): ("mount", "На ножке"),
}

# Во что выбывшее значение разошлось. Разметку товара им не заменить —
# зеркало сделано либо из алюминия, либо из багета, и «либо» тут не
# ответ. А условию посадочной ровно это и нужно: значения одного
# атрибута объединяются по ИЛИ, и «зеркала в раме» — это по-прежнему
# одна страница про обе рамы (ADR-0003)
SUCCESSORS = {
    ("frame", "В раме"): ("Алюминий", "Багет"),
    ("backlight", "С подсветкой"): (
        "Контурная",
        "Фронтальная",
        "Комбинированная",
    ),
}

# Старые атрибуты, которых в наборе владельца нет: после переноса они
# уходят вместе со своим справочником
RETIRED = ("location", "frame-material")

# Значения, выбывшие из справочника оставшихся атрибутов: «В раме» не
# говорит, алюминий это или багет, «С подсветкой» — контурная или
# фронтальная. Разметку по ним прогон снимает, товары — в отчёт
DROPPED = (
    ("frame", "В раме"),
    ("backlight", "С подсветкой"),
)


@dataclass
class Report:
    """Что прогон сделал и что осталось владельцу."""

    carried: int = 0
    strays: dict[str, list[str]] = field(default_factory=dict)
    widened_landings: list[str] = field(default_factory=list)
    cleared: dict[str, list[str]] = field(default_factory=dict)
    unfilled: dict[str, list[str]] = field(default_factory=dict)
    unpublished_landings: list[str] = field(default_factory=list)

    def as_markdown(self) -> str:
        lines = [
            "# Что осталось проставить владельцу (тикет 22)",
            "",
            f"Перенесено разметки скриптом: {self.carried}.",
            "",
        ]
        if self.strays:
            lines += [
                "## Значения вне набора остались у товаров",
                "",
                "Строка справочника, которой в наборе владельца нет, но "
                "которую носят товары. Пустой её не удалить — вместе с "
                "ней ушла бы их разметка. Решите: переназначить товары "
                "и удалить, или дописать значение в набор.",
                "",
            ]
            lines += _sections(self.strays)
        if self.cleared:
            lines += ["## Снято как двусмысленное", ""]
            lines += _sections(self.cleared)
        if self.widened_landings:
            lines += [
                "## Посадочные пересобраны на новые значения",
                "",
                "Условие такой страницы ссылалось на значение, которое "
                "разошлось на несколько. Страница осталась про то же: "
                "значения одного атрибута объединяются по ИЛИ. Тексты "
                "стоит перечитать — они писались про прежний набор.",
                "",
                *(f"- {slug}" for slug in sorted(self.widened_landings)),
                "",
            ]
        if self.unpublished_landings:
            lines += [
                "## Посадочные сняты с публикации",
                "",
                "Условие такой страницы ссылалось на значение, которого "
                "в наборе больше нет. Выберите ей новое условие и "
                "опубликуйте заново — или разведите на несколько "
                "страниц, если одним значением спрос больше не описать.",
                "",
                *(f"- {slug}" for slug in sorted(self.unpublished_landings)),
                "",
            ]
        lines += ["## Не заполнено — калькулятор ждёт", ""]
        lines += _sections(self.unfilled)
        return "\n".join(lines)


def _sections(groups: dict[str, list[str]]) -> list[str]:
    lines: list[str] = []
    for title, slugs in sorted(groups.items()):
        lines.append(f"### {title} — {len(slugs)}")
        lines.append("")
        lines += [f"- {slug}" for slug in sorted(slugs)]
        lines.append("")
    return lines


def run(*, category_slug: str = CATEGORY_SLUG) -> Report:
    """Приводит справочник к набору владельца и переразмечает товары."""
    with transaction.atomic():
        category = Category.objects.get(slug=category_slug)
        attributes = _bring_dictionary(category)
        report = Report()
        moves = _moves(attributes)
        _carry_over(category, moves, report)
        _repoint_landings(moves)
        _drop_ambiguous(attributes, report)
        _retire(category)
        _prune_strays(attributes, report)
        _collect_unfilled(category, report)
        return report


def _bring_dictionary(category: Category) -> dict[str, Attribute]:
    """Заводит недостающее и правит заведённое — до набора владельца.

    Значения не пересоздаются: подпись, уже стоящая у товаров, свои
    связи сохраняет, а прогон правит у неё только признаки. Тариф
    прогон не трогает вовсе — это цифры владельца.
    """
    attributes: dict[str, Attribute] = {}
    for order, spec in enumerate(OWNER_SET):
        attribute, _ = Attribute.objects.update_or_create(
            category=category,
            slug=spec.slug,
            defaults={
                "name": spec.name,
                "kind": spec.kind,
                "is_customer_editable": spec.is_customer_editable,
                "is_filterable": spec.is_filterable,
                "order": order,
            },
        )
        attributes[spec.slug] = attribute
        for value_order, value_spec in enumerate(spec.values):
            AttributeValue.objects.update_or_create(
                attribute=attribute,
                value=value_spec.value,
                defaults={
                    "marks_absence": value_spec.marks_absence,
                    "order": value_order,
                },
            )
    for spec in OWNER_SET:
        attributes[spec.slug].parents.set(
            attributes[parent] for parent in spec.parents
        )
    return attributes


def _moves(
    attributes: dict[str, Attribute],
) -> list[tuple[str, str, AttributeValue]]:
    """Переносы с разрешёнными адресатами: слаг, значение, куда.

    Справочник спрашивается один раз на прогон: тот же список обходят
    и разметка товаров, и условия посадочных.
    """
    return [
        (
            old_slug,
            old_value,
            attributes[new_slug].values.get(value=new_value),
        )
        for (old_slug, old_value), (
            new_slug,
            new_value,
        ) in CARRIED_OVER.items()
    ]


def _carry_over(
    category: Category,
    moves: list[tuple[str, str, AttributeValue]],
    report: Report,
) -> None:
    """Переносит разметку, у которой новый ответ однозначен."""
    for old_slug, old_value, target in moves:
        rows = ProductAttribute.objects.filter(
            product__category=category,
            attribute__slug=old_slug,
            value_option__value=old_value,
        ).select_related("product")
        for row in rows:
            # Владелец мог проставить своё раньше прогона — не спорим.
            # Спорим только с выбывшим значением: «Рама: В раме» на
            # месте алюминия и есть та разметка, которую мы переносим
            existing, created = ProductAttribute.objects.get_or_create(
                product=row.product,
                attribute=target.attribute,
                defaults={"value_option": target},
            )
            if not created and _is_dropped(existing):
                existing.value_option = target
                existing.save(update_fields=["value_option"])
                created = True
            report.carried += int(created)


def _is_dropped(row: ProductAttribute) -> bool:
    """Стоит ли у строки значение, выбывшее из справочника."""
    if row.value_option is None:
        return False
    return (row.attribute.slug, row.value_option.value) in DROPPED


def _repoint_landings(
    moves: list[tuple[str, str, AttributeValue]],
) -> None:
    """Ведёт условия посадочных за переехавшей разметкой.

    «Зеркала напольные» сужают категорию тем же признаком, что и
    раньше, — он просто зовётся теперь «Крепление: На ножке».
    """
    for old_slug, old_value, target in moves:
        LandingCondition.objects.filter(
            attribute__slug=old_slug, value_option__value=old_value
        ).update(attribute=target.attribute, value_option=target)


def _rebuild_landings_on(
    value: AttributeValue,
    successors: tuple[AttributeValue, ...],
    report: Report,
) -> None:
    """Пересобирает условия посадочных, стоявшие на выбывшем значении.

    Значение разошлось на несколько — условие расходится вслед за ним
    и спрашивает их все: «зеркала в раме» это и алюминий, и багет.
    Преемников нет — страницу не на что поставить, и она уходит с
    публикации целой: адрес, заголовок и текст владельца на месте, ему
    остаётся выбрать новое условие.
    """
    conditions = LandingCondition.objects.filter(
        value_option=value
    ).select_related("landing")
    for condition in conditions:
        landing = condition.landing
        if successors and not _would_stop_narrowing(landing, successors):
            report.widened_landings.append(landing.slug)
            for successor in successors:
                LandingCondition.objects.get_or_create(
                    landing=landing,
                    attribute=successor.attribute,
                    value_option=successor,
                )
        else:
            report.unpublished_landings.append(landing.slug)
            landing.is_published = False
            landing.save(update_fields=["is_published"])
    conditions.delete()


def _would_stop_narrowing(
    landing: Landing, successors: tuple[AttributeValue, ...]
) -> bool:
    """Не выйдет ли из пересборки дубль категории.

    Скрипт заводит условия мимо формы, а значит, и мимо её проверки.
    Правило берётся то же самое (`exhausts_dictionary`): перечислив все
    значения атрибута, посадочная перестаёт сужать что бы то ни было, и
    такую страницу лучше снять с публикации, чем выпустить в индекс
    дублем каталога (ADR-0003).
    """
    attribute = successors[0].attribute
    values = {value.pk for value in successors}
    values |= {
        condition.value_option_id
        for condition in landing.conditions.all()
        if condition.attribute_id == attribute.pk
        and condition.value_option_id is not None
    }
    return exhausts_dictionary(attribute, values)


def _drop_ambiguous(attributes: dict[str, Attribute], report: Report) -> None:
    """Снимает разметку, которая в новый набор не переводится.

    Оставить её значило бы соврать справочником: «В раме» на месте
    алюминия сказало бы расчёту, что рамы у зеркала нет вовсе.
    """
    for attribute_slug, value in DROPPED:
        attribute = attributes[attribute_slug]
        dropped = attribute.values.filter(value=value).first()
        if dropped is None:
            continue
        slugs = list(
            ProductAttribute.objects.filter(value_option=dropped).values_list(
                "product__slug", flat=True
            )
        )
        if slugs:
            report.cleared.setdefault(attribute.name, []).extend(slugs)
        ProductAttribute.objects.filter(value_option=dropped).delete()
        successors = tuple(
            attribute.values.get(value=name)
            for name in SUCCESSORS.get((attribute_slug, value), ())
        )
        _rebuild_landings_on(dropped, successors, report)
        dropped.delete()


def _retire(category: Category) -> None:
    """Убирает атрибуты, которых в наборе владельца нет."""
    retired = Attribute.objects.filter(category=category, slug__in=RETIRED)
    ProductAttribute.objects.filter(attribute__in=retired).delete()
    # Условия, которым нашлось новое место, уже переехали; остальные
    # уходят вместе с атрибутом
    LandingCondition.objects.filter(attribute__in=retired).delete()
    retired.delete()


def _prune_strays(attributes: dict[str, Attribute], report: Report) -> None:
    """Доводит справочник до набора: лишнее значение либо уходит, либо видно.

    Приведение к набору — это и значения, а не одни атрибуты: иначе
    справочник остаётся надмножеством таблицы владельца, и в фильтре
    висит значение, которого в наборе нет.

    Незанятое лишнее прогон убирает молча — терять с ним нечего.
    Занятое не трогает: удаление стёрло бы разметку товаров, а решить
    за владельца, куда её переназначить, нельзя.
    """
    wanted = {
        (spec.slug, value.value) for spec in OWNER_SET for value in spec.values
    }
    for slug, attribute in attributes.items():
        for value in attribute.values.all():
            if (slug, value.value) in wanted:
                continue
            holders = _holders_of(value)
            if holders:
                report.strays.setdefault(value.full_label, []).extend(holders)
            else:
                value.delete()


def _holders_of(value: AttributeValue) -> list[str]:
    """Кто держит значение: товары, их варианты и условия посадочных.

    Спрашиваются все трое, а не одни товары: значение под защитой
    внешнего ключа, и удаление занятого упало бы посреди прогона.
    """
    return [
        *value.product_assignments.values_list("product__slug", flat=True),
        *value.variant_selections.values_list("product__slug", flat=True),
        *value.landing_conditions.values_list("landing__slug", flat=True),
    ]


def _collect_unfilled(category: Category, report: Report) -> None:
    """Собирает, какого атрибута какому товару не хватает до расчёта.

    Спрашивается тот самый гейт, который включает калькулятор, — иначе
    отчёт звал бы владельца заполнить кнопку у зеркала без подсветки
    и без подогрева, где её не бывает вовсе.
    """
    products = category.products.prefetch_related(tariffs.product_values())
    for product in products:
        for gap in calculator.missing_for_calculation(product):
            report.unfilled.setdefault(gap, []).append(product.slug)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--overwrite-report",
        action="store_true",
        help="Переписать существующий отчёт.",
    )
    arguments = parser.parse_args()
    # Отчёт — не побочный вывод, а результат прогона: только он помнит,
    # у каких товаров разметку сняли и какие посадочные пересобрали.
    # Второму прогону вспомнить это неоткуда, и молча затерев файл, он
    # унёс бы единственный список работ владельца
    if arguments.report.exists() and not arguments.overwrite_report:
        parser.error(
            f"Отчёт {arguments.report} уже есть — его писал прогон, "
            "который переносил разметку. Возьмите --report с другим "
            "именем или --overwrite-report, если тот отчёт не нужен."
        )
    report = run()
    arguments.report.write_text(report.as_markdown(), encoding="utf-8")
    print(f"Перенесено строк разметки: {report.carried}")
    print(f"Отчёт владельцу: {arguments.report}")


if __name__ == "__main__":
    main()
