"""Одноразовый перенос каталога memiro.ru в новую модель (тикет 11).

Скрипт живёт вне кодовой базы: это разовая операция, не продукт.
Запуск из корня репозитория:

    uv run python .scratch/new-site/migration/migrate.py [--reset]
        [--overwrite]

На входе — выгрузки со старого сервера (`catalog.json`, `media.json`)
и распакованные файлы `uploads/`. На выходе — товары-черновики в базе,
`legacy-map.json` для `manage.py import_legacy_urls` и отчёт
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
from typing import Any
from urllib.parse import unquote, urlsplit

import django

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memiro.settings")
django.setup()

from django.core.files import File  # noqa: E402
from django.db import transaction  # noqa: E402
from django.db.models.fields.files import ImageFieldFile  # noqa: E402
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

# Запись выгрузки со старого сайта, как её отдал экспортёр: разбирать
# её вслепую больше нигде не нужно — этим занят LegacyProduct
LegacyRecord = dict[str, Any]

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

# Страницы старого сайта, у которых на новом есть свой адрес.
# Всё остальное, что выгружено и сюда не попало, уезжает на 410:
# лучше честное «страницы больше нет», чем молчаливый 404
PAGE_MOVES = {
    "/privacy-policy/": "/privacy/",
    "/about-us/": "/about/",
    "/delivery-payment-and-services/": "/delivery/",
    "/contacts/": "/contacts/",
}

# Адреса, которые не менялись: главная и корень каталога. Правило на
# самого себя стало бы петлёй, если страница когда-нибудь отдаст 404
PAGES_KEPT = ("/", "/catalog/")

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


@dataclass(frozen=True)
class LegacyProduct:
    """Товар старого сайта: разбор его полей собран в одном месте.

    Экспортёр отдаёт запись словарём как есть — знание о том, где
    у WordPress что лежит, живёт здесь и больше нигде.
    """

    record: LegacyRecord

    @property
    def slug(self) -> str:
        return str(self.record["slug"])

    @property
    def title(self) -> str:
        return str(self.record["title"])

    def acf(self, key: str) -> str:
        """Значение ACF-поля; пустая строка, если поля нет.

        WordPress хранит мету списком значений на ключ — у полей
        каталога значение всегда одно.
        """
        values = self.record["meta"].get(key) or []
        value = values[0] if values else ""
        return value if isinstance(value, str) else ""

    @property
    def gallery_ids(self) -> list[str]:
        values = self.record["meta"].get("gallery") or []
        ids = values[0] if values else []
        return [str(value) for value in ids] if isinstance(ids, list) else []

    def warn(self, message: str) -> str:
        """Предупреждение прогона, подписанное слагом товара."""
        return f"{self.slug}: {message}"

    @property
    def created_at(self) -> datetime:
        """Дата публикации на старом сайте — по времени сервера (МСК)."""
        stamp = parse_datetime(str(self.record["date"]))
        if stamp is None:
            message = self.warn(f"не разобрать дату {self.record['date']!r}")
            raise ValueError(message)
        return make_aware(stamp)

    @property
    def price(self) -> int | None:
        """Цена числом; None — на старом сайте «Цена по запросу».

        Второй `replace` убирает неразрывный пробел: цены набирались
        руками, и разряды разделены то одним пробелом, то другим.
        """
        raw = self.acf("price").replace(" ", "").replace(" ", "")
        return int(raw) if raw.isdigit() and int(raw) > 0 else None


class Media:
    """Файлы вложений старого сайта, распакованные в `uploads/`."""

    def __init__(self, export: LegacyRecord, root: Path) -> None:
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


def build_category(
    items: list[LegacyProduct],
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
        used = {item.acf(spec.field) for item in items}
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


def save_image(field: ImageFieldFile, path: Path) -> None:
    """Кладёт файл старого сайта в поле изображения, не сохраняя запись."""
    with path.open("rb") as handle:
        field.save(path.name, File(handle), save=False)


def attach_photos(
    product: Product, item: LegacyProduct, media: Media
) -> list[str]:
    """Главное фото в двух размерах и галерея; возвращает предупреждения."""
    warnings: list[str] = []
    image_id = item.acf("img")
    large = media.original(image_id) if image_id else None
    small = media.card(image_id) if image_id else None
    if large is None or small is None:
        warnings.append(item.warn("нет файла главного фото"))
    # Повторный прогон иначе оставит прежние файлы сиротами:
    # ImageField.save() кладёт новый файл рядом, старый не трогает
    product.photo_large.delete(save=False)
    product.photo_small.delete(save=False)
    if large is not None:
        save_image(product.photo_large, large)
    if small is not None:
        save_image(product.photo_small, small)
    product.save()

    for image in product.gallery.all():
        image.image.delete(save=False)
        image.delete()
    for order, attachment_id in enumerate(item.gallery_ids):
        path = media.original(attachment_id)
        if path is None:
            warnings.append(item.warn(f"нет файла галереи {attachment_id}"))
            continue
        image = ProductImage(product=product, order=order)
        save_image(image.image, path)
        image.save()
    return warnings


def attach_attributes(
    product: Product,
    item: LegacyProduct,
    attributes: dict[str, Attribute],
) -> list[str]:
    warnings: list[str] = []
    product.attribute_values.all().delete()
    for spec in ATTRIBUTES:
        token = item.acf(spec.field)
        if not token:
            continue
        label = spec.label_for(token)
        if label is None:
            warnings.append(
                item.warn(f"{spec.field}={token} нет в справочнике")
            )
            continue
        attribute = attributes[spec.field]
        option = AttributeValue.objects.get(attribute=attribute, value=label)
        ProductAttribute.objects.create(
            product=product, attribute=attribute, value_option=option
        )
    return warnings


def product_fields(
    item: LegacyProduct, category: Category, order: int
) -> dict[str, object]:
    """Поля товара новой модели по записи старого сайта."""
    return {
        "category": category,
        "name": item.title,
        "price": item.price or PRICE_STUB,
        "description": item.acf("desc"),
        "article": item.acf("sku"),
        "is_popular": item.acf("popular") == "1",
        "is_promo": item.acf("akciya") == "1",
        # Владелец публикует после вычитки — перенос не решает за него,
        # что уже готово к витрине
        "is_published": False,
        # Витринный порядок задаётся порядком выгрузки: своего у старого
        # сайта не было, а владелец перетасует товары в админке
        "order": order,
    }


def import_products(
    items: list[LegacyProduct],
    category: Category,
    attributes: dict[str, Attribute],
    media: Media,
    *,
    overwrite: bool,
) -> tuple[list[str], list[str]]:
    """Заводит товары-черновики.

    Возвращает предупреждения прогона и слаги пропущенных товаров.
    Уже заведённый товар по умолчанию пропускается: перенос разовый, и
    второй прогон иначе вернул бы заглушку 1 ₽ поверх проставленной
    владельцем цены и снял бы с витрины опубликованное. Переписать
    заведённое — явное `--overwrite`.
    """
    warnings: list[str] = []
    skipped: list[str] = []
    for order, item in enumerate(items):
        fields = product_fields(item, category, order)
        product, created = Product.objects.update_or_create(
            slug=item.slug, create_defaults=fields, defaults={}
        )
        if not created:
            if not overwrite:
                skipped.append(item.slug)
                continue
            for name, value in fields.items():
                setattr(product, name, value)
            product.save()
        warnings += attach_photos(product, item, media)
        warnings += attach_attributes(product, item, attributes)
        # `created_at` заполняется auto_now_add: без переноса даты
        # сортировка «новинки» показала бы порядок импорта. Апдейт идёт
        # последним — `save()` внутри attach_photos вернул бы дату вставки
        Product.objects.filter(pk=product.pk).update(
            created_at=item.created_at
        )
    return warnings, skipped


def legacy_paths(record: LegacyRecord) -> list[str]:
    """Все адреса, по которым запись отдавалась на старом сайте.

    Текущий адрес берётся из выгрузки, а не собирается из префикса
    руками: экспортёр знает пермалинки точно. Следом идут прежние
    слаги (`_wp_old_slug`) — WordPress отдавал их 301-м, и они сидят
    в индексе. В карту всё попадает раскодированным: `request.path`
    в Django уже раскодирован.
    """
    path = urlsplit(str(record["url"])).path
    prefix = path.rsplit("/", 2)[0]
    return [
        path,
        *(
            f"{prefix}/{unquote(value)}/"
            for value in record["meta"].get("_wp_old_slug") or []
            if isinstance(value, str) and value
        ),
    ]


def build_legacy_map(export: LegacyRecord) -> LegacyRecord:
    """Карта переезда в формате команды `import_legacy_urls`.

    Ключи `redirects`/`gone` диктует та команда (`CONTEXT.md`,
    «Адрес старого сайта»). Обходятся все выгруженные записи: страница,
    которой не нашлось адреса на новом сайте, уезжает на 410 — это
    честнее молчаливого 404.
    """
    moved: dict[str, str] = {}
    gone: list[str] = []
    for item in map(LegacyProduct, export["items"]):
        target = f"/catalog/{CATEGORY_SLUG}/{item.slug}/"
        for path in legacy_paths(item.record):
            moved[path] = target
    for bucket in ("pages", "posts", "faq"):
        for record in export[bucket]:
            current, *previous = legacy_paths(record)
            # У адреса, который не менялся, правило нужно только
            # прежним слагам: на самого себя оно стало бы петлёй
            target = PAGE_MOVES.get(
                current, current if current in PAGES_KEPT else ""
            )
            paths = previous if current in PAGES_KEPT else [current, *previous]
            for path in paths:
                if target:
                    moved[path] = target
                elif path not in gone:
                    gone.append(path)
    return {"redirects": moved, "gone": gone}


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


def load(name: str) -> LegacyRecord:
    """Выгрузка со старого сервера, лежащая рядом со скриптом."""
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="удалить демо-категории и их товары перед переносом",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "переписать уже заведённые товары выгрузкой; без флага они "
            "пропускаются, чтобы не затереть правки владельца"
        ),
    )
    options = parser.parse_args()

    export = load("catalog.json")
    media = Media(load("media.json"), HERE / "uploads")
    items = [LegacyProduct(record) for record in export["items"]]

    with transaction.atomic():
        category, attributes = build_category(items)
        if options.reset:
            reset_demo()
        warnings, skipped = import_products(
            items,
            category,
            attributes,
            media,
            overwrite=options.overwrite,
        )

    legacy_map = build_legacy_map(export)
    (HERE / "legacy-map.json").write_text(
        json.dumps(legacy_map, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    unpriced = list(
        Product.objects.filter(category=category, price=PRICE_STUB)
    )
    (HERE / "price-missing.md").write_text(
        price_report(unpriced), encoding="utf-8"
    )

    print(f"Товаров заведено: {len(items) - len(skipped)} из {len(items)}")
    if skipped:
        print(f"Пропущено (уже заведены, нужен --overwrite): {len(skipped)}")
    print(f"Без цены (заглушка {PRICE_STUB} \u20bd): {len(unpriced)}")
    print(
        f"Правил переезда: {len(legacy_map['redirects'])} на 301, "
        f"{len(legacy_map['gone'])} на 410"
    )
    for warning in warnings:
        print(f"  ! {warning}")


if __name__ == "__main__":
    main()
