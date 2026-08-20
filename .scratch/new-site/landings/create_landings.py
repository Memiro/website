"""Шесть посадочных из макета v2 — плитки витрины (тикет 14).

Заведение данных, а не продукт: скрипт живёт вне кодовой базы, как и
перенос каталога. Запуск из корня репозитория:

    uv run python .scratch/new-site/landings/create_landings.py

Повторный прогон безопасен: посадочная с таким слагом пропускается —
владелец правит тексты и обложки в админке, и переписывать их выгрузкой
нельзя.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import django

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memiro.settings")
django.setup()

from django.db import transaction  # noqa: E402

from memiro.catalog.models import (  # noqa: E402
    Attribute,
    AttributeValue,
    Category,
    Landing,
    LandingCondition,
)

CATEGORY_SLUG = "zerkala"


@dataclass(frozen=True)
class Plan:
    """Посадочная и её единственное условие (слаг атрибута, значение)."""

    slug: str
    heading: str
    title: str
    description: str
    text: str
    attribute: str
    value: str


# Порядок — как в блоке «Каталог» макета v2
PLANS = (
    Plan(
        slug="zerkala-v-rame",
        heading="Зеркала в раме",
        title="Зеркала в раме на заказ в Санкт-Петербурге — memiro",
        description=(
            "Зеркала в раме на заказ: алюминий и металл, чёрный, белый, "
            "золото, серебро. Производство и установка в Петербурге."
        ),
        text=(
            "Рама задаёт характер зеркала и закрывает кромку. Профиль "
            "и цвет подбираем под фурнитуру комнаты — от матового "
            "чёрного до тёплого золота."
        ),
        attribute="frame",
        value="В раме",
    ),
    Plan(
        slug="zerkala-bez-ramy",
        heading="Зеркала без рамы",
        title="Зеркала без рамы на заказ в Санкт-Петербурге — memiro",
        description=(
            "Зеркала без рамы на заказ по вашим размерам: шлифованная "
            "кромка, скрытое крепление. Собственное производство memiro."
        ),
        text=(
            "Без рамы зеркало читается как часть стены. Кромку шлифуем "
            "и полируем, крепление делаем скрытым, поэтому полотно "
            "выглядит цельным."
        ),
        attribute="frame",
        value="Без рамы",
    ),
    Plan(
        slug="kruglye-zerkala",
        heading="Круглые зеркала",
        title="Круглые зеркала на заказ в Санкт-Петербурге — memiro",
        description=(
            "Круглые зеркала на заказ по вашему диаметру: с подсветкой "
            "и без, в раме и без рамы. Производство, доставка, монтаж."
        ),
        text=(
            "Круг смягчает геометрию комнаты и хорошо работает в "
            "прихожей и ванной. Диаметр задаёте вы — от небольшого "
            "надраковинного до ростового."
        ),
        attribute="form",
        value="Круглое",
    ),
    Plan(
        slug="figurnye-zerkala",
        heading="Фигурные зеркала",
        title="Фигурные зеркала на заказ в Санкт-Петербурге — memiro",
        description=(
            "Фигурные зеркала на заказ: арка, капля, полукруг, форма по "
            "вашему эскизу. Собственное производство memiro."
        ),
        text=(
            "Арка, капля, полусфера или контур по вашему эскизу — режем "
            "и обрабатываем кромку сами, поэтому форма ограничена "
            "только размерами полотна."
        ),
        attribute="form",
        value="Фигурное",
    ),
    Plan(
        slug="zerkala-s-podsvetkoy",
        heading="Зеркала с подсветкой",
        title="Зеркала с подсветкой на заказ в Санкт-Петербурге — memiro",
        description=(
            "Зеркала с подсветкой на заказ по вашим размерам. Контурная "
            "и фронтальная подсветка, собственное производство memiro."
        ),
        text=(
            "Подсветка по контуру даёт ровный мягкий свет и не слепит, "
            "фронтальная — освещает лицо без теней. Размер, форму и "
            "температуру света подбираем под ваш интерьер."
        ),
        attribute="backlight",
        value="С подсветкой",
    ),
    Plan(
        slug="zerkala-napolnye",
        heading="Зеркала напольные",
        title="Напольные зеркала на заказ в Санкт-Петербурге — memiro",
        description=(
            "Напольные зеркала в полный рост на заказ по вашим "
            "размерам. Устойчивая опора, доставка и установка."
        ),
        text=(
            "Ростовое зеркало на опоре не требует сверления стены и "
            "переезжает вместе с вами. Высоту и наклон подбираем под "
            "рост и место."
        ),
        attribute="location",
        value="Напольное",
    ),
)


def main() -> None:
    category = Category.objects.get(slug=CATEGORY_SLUG)
    with transaction.atomic():
        for order, plan in enumerate(PLANS):
            if Landing.objects.filter(slug=plan.slug).exists():
                print(f"= {plan.slug}: уже заведена, пропуск")
                continue
            attribute = Attribute.objects.get(
                category=category, slug=plan.attribute
            )
            value = AttributeValue.objects.get(
                attribute=attribute, value=plan.value
            )
            landing = Landing.objects.create(
                category=category,
                slug=plan.slug,
                title=plan.title,
                heading=plan.heading,
                description=plan.description,
                text=plan.text,
                is_published=True,
                order=order,
            )
            LandingCondition.objects.create(
                landing=landing, attribute=attribute, value_option=value
            )
            print(f"+ {plan.slug}: {plan.heading}")


if __name__ == "__main__":
    main()
