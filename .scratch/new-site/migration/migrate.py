"""Одноразовый перенос каталога memiro.ru в новую модель (тикет 11).

Скрипт живёт вне кодовой базы: это разовая операция, не продукт.
Запуск из корня репозитория:

    uv run python .scratch/new-site/migration/migrate.py [--reset]

На входе — выгрузки со старого сервера (`catalog.json`, `media.json`)
и распакованные файлы `uploads/`. На выходе — товары-черновики в базе,
`redirects.json` для `manage.py import_legacy_urls` и отчёт
`price-missing.md` со списком товаров без цены.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import django

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memiro.settings")
django.setup()

from django.core.files import File  # noqa: E402
from django.db import transaction  # noqa: E402
from django.utils.dateparse import parse_datetime  # noqa: E402
from django.utils.timezone import make_aware  # noqa: E402

from memiro.catalog.models import (  # noqa: E402
    Attribute,
    AttributeValue,
    Category,
    Product,
    ProductAttribute,
    ProductImage,
)

# Категория новой модели — тип товара, а не форма или рама
# (CONTEXT.md): все 88 зеркал старого сайта ложатся в одну.
CATEGORY_NAME = "Зеркала"
CATEGORY_SLUG = "zerkala"


@dataclass(frozen=True)
class AttributeSpec:
    """Поле ACF старого сайта в виде атрибута новой категории.

    `choices` — токен старого поля → подпись значения. Подписи взяты из
    определений ACF (`export_acf.php`), не выдуманы.
    """

    field: str
    label: str
    choices: dict[str, str]

    def label_for(self, token: str) -> str | None:
        return self.choices.get(token)


ATTRIBUTES = (
    AttributeSpec(
        "location",
        "Расположение",
        {"nastennoe": "Настенное", "napolnoe": "Напольное"},
    ),
    AttributeSpec(
        "form",
        "Форма",
        {
            "pryamougolnoe": "Прямоугольное",
            "krugloe": "Круглое",
            "figurnoe": "Фигурное",
        },
    ),
    AttributeSpec(
        "backlight",
        "Подсветка",
        {"s-podsvetkoj": "С подсветкой", "bez-podsvetki": "Без подсветки"},
    ),
    AttributeSpec(
        "frame", "Рама", {"v-rame": "В раме", "bez-ramy": "Без рамы"}
    ),
    AttributeSpec(
        "frame-color",
        "Цвет рамы",
        {
            "chernyj": "Чёрный",
            "belyj": "Белый",
            "zoloto": "Золото",
            "serebro": "Серебро",
            "bronza": "Бронза",
            "goluboj": "Голубой",
            "derevo": "Дерево",
            "drugoe": "Другое",
        },
    ),
    AttributeSpec(
        "frame-material",
        "Материал рамы",
        {
            "alyuminij": "Алюминий",
            "metall": "Металл",
            "plastik": "Пластик",
            "derevo": "Дерево",
            "drugoe": "Другое",
        },
    ),
)

# Цена-заглушка товарам, у которых на старом сайте стояло «Цена по
# запросу»: в новой модели цена обязательна. Такой товар остаётся
# черновиком и попадает в отчёт — на витрину заглушка не выходит.
PRICE_STUB = 1

# Старый сайт отдавал карточки товара по этому префиксу
LEGACY_PRODUCT_PREFIX = "/mirrors/"

# Статические страницы старого сайта: путь → маршрут нового. `/` и
# `/catalog/` в карте не нужны: адрес не сменился, а правило на самого
# себя стало бы петлёй, если страница когда-нибудь отдаст 404
LEGACY_PAGES = {
    "/privacy-policy/": "/privacy/",
    "/about-us/": "/about/",
    "/delivery-payment-and-services/": "/delivery/",
    "/contacts/": "/contacts/",
}

# Страницы, которым переезжать некуда: 410, а не 301 на главную
LEGACY_GONE = ("/testovaya-stranicza/", "/privet-mir/")

# Вопросы FAQ старого сайта жили отдельными страницами по этому
# префиксу. Контент вопросов тикет не переносит, а на новом сайте FAQ —
# блок главной, отдельных адресов у вопросов нет: значит 410
LEGACY_FAQ_PREFIX = "/faq/"

# Демо-категории, которыми витрина жила до переноса: их сносит --reset.
# Список явный, чтобы прогон не задел настоящую категорию, которую
# владелец мог завести сам (например душевые перегородки)
DEMO_CATEGORIES = (
    "v-rame",
    "figurnye",
    "s-podsvetkoy",
    "kruglye",
    "napolnye",
    "arki",
)


def acf(item: dict, key: str) -> str:
    """Значение ACF-поля старого сайта; пустая строка, если нет.

    WordPress хранит мету списком значений на ключ — у полей каталога
    значение всегда одно.
    """
    values = item["meta"].get(key) or []
    value = values[0] if values else ""
    return value if isinstance(value, str) else ""


def gallery_ids(item: dict) -> list[str]:
    values = item["meta"].get("gallery") or []
    ids = values[0] if values else []
    return [str(value) for value in ids] if isinstance(ids, list) else []


def old_slugs(item: dict) -> list[str]:
    """Прежние слаги товара, которые WordPress сам отдавал 301-м.

    У 23 зеркал слаг когда-то был кириллическим; эти адреса сидят
    в индексе, и без них переезд теряет их вес. В карту они идут
    раскодированными: `request.path` в Django уже раскодирован.
    """
    return [
        unquote(value)
        for value in item["meta"].get("_wp_old_slug") or []
        if isinstance(value, str) and value
    ]


def price_of(item: dict) -> int | None:
    """Цена старого сайта числом; None — «Цена по запросу»."""
    raw = acf(item, "price").replace(" ", "").replace(" ", "")
    return int(raw) if raw.isdigit() and int(raw) > 0 else None


def created_at(item: dict) -> datetime:
    """Дата публикации на старом сайте — по времени сервера (МСК)."""
    stamp = parse_datetime(item["date"])
    if stamp is None:
        message = f"{item['slug']}: не разобрать дату {item['date']!r}"
        raise ValueError(message)
    return make_aware(stamp)


class Media:
    """Файлы вложений старого сайта, распакованные в `uploads/`."""

    def __init__(self, export: dict, root: Path) -> None:
        self.attachments = export["attachments"]
        self.root = root

    def _path(self, relative: str) -> Path | None:
        path = self.root / relative
        return path if path.is_file() else None

    def original(self, attachment_id: str) -> Path | None:
        attachment = self.attachments.get(str(attachment_id))
        return self._path(attachment["file"]) if attachment else None

    def card(self, attachment_id: str) -> Path | None:
        """Кадр под плитку каталога: размер WP `medium_large` (768px).

        Оригиналы весят до нескольких мегабайт — в плитку они не идут.
        """
        attachment = self.attachments.get(str(attachment_id))
        if not attachment:
            return None
        size = attachment["sizes"].get("medium_large")
        if not size:
            return self.original(attachment_id)
        return self._path(size["file"])


def build_taxonomy(
    items: list[dict],
) -> tuple[Category, dict[str, Attribute]]:
    """Категория с атрибутами и справочниками значений.

    В справочник попадают только значения, встретившиеся в данных:
    словарь ACF знает и «Дерево», но ни одно зеркало старого сайта его
    не носит, а пустое значение фильтра — мусор в сайдбаре каталога.
    """
    category, _ = Category.objects.update_or_create(
        slug=CATEGORY_SLUG, defaults={"name": CATEGORY_NAME, "order": 0}
    )
    attributes: dict[str, Attribute] = {}
    for order, spec in enumerate(ATTRIBUTES):
        attribute, _ = Attribute.objects.update_or_create(
            category=category,
            slug=spec.field,
            defaults={
                "name": spec.label,
                "kind": Attribute.Kind.CHOICE,
                "order": order,
            },
        )
        used = {acf(item, spec.field) for item in items}
        for value_order, (token, value) in enumerate(spec.choices.items()):
            if token not in used:
                continue
            AttributeValue.objects.update_or_create(
                attribute=attribute,
                value=value,
                defaults={"order": value_order},
            )
        attributes[spec.field] = attribute
    return category, attributes


def attach_photos(product: Product, item: dict, media: Media) -> list[str]:
    """Главное фото в двух размерах и галерея; возвращает предупреждения."""
    warnings: list[str] = []
    image_id = acf(item, "img")
    large = media.original(image_id) if image_id else None
    small = media.card(image_id) if image_id else None
    if large is None or small is None:
        warnings.append(f"{item['slug']}: нет файла главного фото")
    # Повторный прогон иначе оставит прежние файлы сиротами:
    # ImageField.save() кладёт новый файл рядом, старый не трогает
    product.photo_large.delete(save=False)
    product.photo_small.delete(save=False)
    if large is not None:
        with large.open("rb") as handle:
            product.photo_large.save(large.name, File(handle), save=False)
    if small is not None:
        with small.open("rb") as handle:
            product.photo_small.save(small.name, File(handle), save=False)
    product.save()

    for image in product.gallery.all():
        image.image.delete(save=False)
        image.delete()
    for order, attachment_id in enumerate(gallery_ids(item)):
        path = media.original(attachment_id)
        if path is None:
            warnings.append(
                f"{item['slug']}: нет файла галереи {attachment_id}"
            )
            continue
        image = ProductImage(product=product, order=order)
        with path.open("rb") as handle:
            image.image.save(path.name, File(handle), save=False)
        image.save()
    return warnings


def attach_attributes(
    product: Product, item: dict, attributes: dict[str, Attribute]
) -> list[str]:
    warnings: list[str] = []
    product.attribute_values.all().delete()
    for spec in ATTRIBUTES:
        token = acf(item, spec.field)
        if not token:
            continue
        label = spec.label_for(token)
        if label is None:
            warnings.append(
                f"{item['slug']}: {spec.field}={token} нет в справочнике"
            )
            continue
        attribute = attributes[spec.field]
        option = AttributeValue.objects.get(attribute=attribute, value=label)
        ProductAttribute.objects.create(
            product=product, attribute=attribute, value_option=option
        )
    return warnings


def import_products(
    items: list[dict],
    category: Category,
    attributes: dict[str, Attribute],
    media: Media,
) -> tuple[list[str], list[Product]]:
    warnings: list[str] = []
    unpriced: list[Product] = []
    for order, item in enumerate(items):
        price = price_of(item)
        product, _ = Product.objects.update_or_create(
            slug=item["slug"],
            defaults={
                "category": category,
                "name": item["title"],
                "price": price or PRICE_STUB,
                "description": acf(item, "desc"),
                "article": acf(item, "sku"),
                "is_popular": acf(item, "popular") == "1",
                "is_promo": acf(item, "akciya") == "1",
                # Владелец публикует после вычитки — перенос не решает
                # за него, что уже готово к витрине
                "is_published": False,
                "order": order,
            },
        )
        if price is None:
            unpriced.append(product)
        warnings += attach_photos(product, item, media)
        warnings += attach_attributes(product, item, attributes)
        # `created_at` заполняется auto_now_add: без переноса даты
        # сортировка «новинки» показала бы порядок импорта. Апдейт идёт
        # последним — `save()` внутри attach_photos вернул бы дату вставки
        Product.objects.filter(pk=product.pk).update(
            created_at=created_at(item)
        )
    return warnings, unpriced


def build_legacy_map(items: list[dict], faq: list[dict]) -> dict:
    """Карта переезда в формате команды `import_legacy_urls`.

    Ключи `redirects`/`gone` диктует та команда (`CONTEXT.md`,
    «Адрес старого сайта»).
    """
    rules: dict[str, str] = {}
    for item in items:
        target = f"/catalog/{CATEGORY_SLUG}/{item['slug']}/"
        for slug in [item["slug"], *old_slugs(item)]:
            rules[f"{LEGACY_PRODUCT_PREFIX}{slug}/"] = target
    rules.update(LEGACY_PAGES)
    gone = [
        *LEGACY_GONE,
        *(f"{LEGACY_FAQ_PREFIX}{entry['slug']}/" for entry in faq),
    ]
    return {"redirects": rules, "gone": gone}


def price_report(unpriced: list[Product]) -> str:
    lines = [
        "# Товары без цены после переноса",
        "",
        (
            "На старом сайте у них стояло «Цена по запросу»; в новой "
            "модели цена обязательна, поэтому при переносе проставлена "
            f"заглушка {PRICE_STUB} ₽. Товары остаются черновиками — "
            "заглушка на витрину не выходит. Владельцу нужно проставить "
            "цены в админке и опубликовать."
        ),
        "",
        f"Всего: {len(unpriced)}",
        "",
    ]
    lines += [
        f"- [{product.name}](/admin/catalog/product/{product.pk}/change/)"
        for product in unpriced
    ]
    return "\n".join(lines) + "\n"


def reset_demo() -> None:
    """Убирает демо-данные, которыми жила витрина до переноса.

    Список демо-категорий явный: настоящую категорию, которую владелец
    мог завести сам, прогон трогать не должен.
    """
    demo = Category.objects.filter(slug__in=DEMO_CATEGORIES)
    products = Product.objects.filter(category__in=demo)
    # Django не удаляет файлы вслед за записью — иначе демо-фото
    # остались бы в `media/` сиротами
    for image in ProductImage.objects.filter(product__in=products):
        image.image.delete(save=False)
    for product in products:
        product.photo_large.delete(save=False)
        product.photo_small.delete(save=False)
    products.delete()
    demo.delete()


def load(name: str) -> dict:
    """Выгрузка со старого сервера, лежащая рядом со скриптом."""
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="удалить демо-категории и их товары перед переносом",
    )
    options = parser.parse_args()

    export = load("catalog.json")
    media = Media(load("media.json"), HERE / "uploads")
    items = export["items"]

    with transaction.atomic():
        category, attributes = build_taxonomy(items)
        if options.reset:
            reset_demo()
        warnings, unpriced = import_products(
            items, category, attributes, media
        )

    legacy_map = build_legacy_map(items, export["faq"])
    (HERE / "redirects.json").write_text(
        json.dumps(legacy_map, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (HERE / "price-missing.md").write_text(
        price_report(unpriced), encoding="utf-8"
    )

    print(f"Товаров перенесено: {len(items)}")
    print(f"Без цены (заглушка {PRICE_STUB} ₽): {len(unpriced)}")
    print(
        f"Правил переезда: {len(legacy_map['redirects'])} на 301, "
        f"{len(legacy_map['gone'])} на 410"
    )
    for warning in warnings:
        print(f"  ! {warning}")


if __name__ == "__main__":
    main()
