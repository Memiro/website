"""Книга расчёта из живых данных — файлом, который открывают таблицей.

    just manage pricing_workbook
    just manage pricing_workbook --product zerkalo-arka-nave
    just manage pricing_workbook --category zerkala -o /tmp/prices.xlsx

Книга собирается на каждый запуск заново: тарифы в ней устаревают в тот
же день, когда владелец правит справочник, и файла в репозитории нет
намеренно (`catalog/workbook.py`).

Товар не обязателен, но с ним книга полезнее: его разметка становится
умолчаниями калькулятора, а лист «Сверка» получает итоги движка, по
которым видно, совпадает ли книга с сайтом.

Читает и не пишет: команду можно звать на боевой базе.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand, CommandError

from memiro.catalog import tariffs, workbook
from memiro.catalog.models import Category, Product

if TYPE_CHECKING:
    from argparse import ArgumentParser

DEFAULT_PATH = "pricing-workbook.xlsx"


class Command(BaseCommand):
    help = "Собирает книгу расчёта цены из данных админки"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--category",
            help="слаг категории; по умолчанию — первая с атрибутами",
        )
        parser.add_argument(
            "--product",
            help="слаг товара: его разметка станет умолчаниями книги",
        )
        parser.add_argument(
            "-o",
            "--output",
            default=DEFAULT_PATH,
            help=f"куда положить файл (по умолчанию {DEFAULT_PATH})",
        )

    def handle(self, *args: object, **options: str | None) -> None:  # noqa: ARG002
        product = _product(options["product"])
        category = _category(options["category"], product)
        path = options["output"] or DEFAULT_PATH
        workbook.write(category, path, product=product)
        self.stdout.write(
            f"Книга собрана: {path}\n"
            f"  категория: {category.name}\n"
            f"  товар: {product.name if product else '— не назван'}"
        )


def _product(slug: str | None) -> Product | None:
    """Товар вместе с разметкой — тем же префетчем, что и расчёт."""
    if not slug:
        return None
    found = (
        Product.objects.filter(slug=slug)
        .select_related("category")
        .prefetch_related(tariffs.product_values())
        .first()
    )
    if found is None:
        message = f"Товара со слагом «{slug}» нет."
        raise CommandError(message)
    return found


def _category(slug: str | None, product: Product | None) -> Category:
    """Категория из аргумента, из товара или первая подходящая.

    «Первая подходящая» — та, у которой есть атрибуты: без них книга
    вышла бы с пустым расчётом, а причина осталась бы непонятной.
    """
    if slug:
        found = Category.objects.filter(slug=slug).first()
        if found is None:
            message = f"Категории со слагом «{slug}» нет."
            raise CommandError(message)
        return found
    if product is not None:
        return product.category
    found = Category.objects.filter(attributes__isnull=False).first()
    if found is None:
        message = (
            "Ни у одной категории нет атрибутов — собирать книгу не из "
            "чего. Заведите их в админке или укажите --category."
        )
        raise CommandError(message)
    return found
