"""JSON-эндпоинты пути до заявки: подборка товаров и приём заявки."""

from __future__ import annotations

from http import HTTPStatus
from typing import Annotated, ClassVar, Literal, NamedTuple

import pydantic
from django.db import transaction
from django.urls import reverse
from dmr import Body, Controller, Query, modify
from dmr.plugins.pydantic import PydanticSerializer

from memiro.api.csrf import csrf_protect_json
from memiro.api.errors import UNPROCESSABLE, reject
from memiro.api.ids import IDS_PATTERN, MAX_IDS_LENGTH, parse_ids
from memiro.catalog import quoting
from memiro.catalog.models import Product
from memiro.inquiries.limits import (
    MAX_ITEMS,
    MAX_WISH_LENGTH,
    MIN_PHONE_DIGITS,
)
from memiro.inquiries.models import Inquiry, InquiryItem
from memiro.inquiries.notifications import notify
from memiro.legal.privacy import PRIVACY_VERSION

# Телефон принимаем в любом человеческом написании: цифры, скобки,
# плюс, пробелы и дефисы. Нормализацией занимается менеджер, не сайт
PHONE_PATTERN = r"^[\d\s()+\-]{6,32}$"
# Пустая строка — «не указан»; иначе минимальная форма адреса
EMAIL_PATTERN = r"^$|^[^@\s]+@[^@\s]+\.[^@\s]{2,}$"
# Обрезка пробелов до проверки длины: «   » — пустое имя, а не двухсимвольное
Trimmed = pydantic.StringConstraints(strip_whitespace=True)

# Потолки присланного расчёта — не правила расчёта, а границы того,
# что не жалко записать в журнал: миллиметр в десятизначном числе и
# список значений вчетверо длиннее любого справочника. Всё, что
# расчёту не годится, отсеет он сам, не отменяя заявки
MAX_STORED_SIDE_MM = 1_000_000_000
MAX_STORED_VALUES = 200
StoredSide = Annotated[int, pydantic.Field(ge=1, le=MAX_STORED_SIDE_MM)]


class ProductSummary(pydantic.BaseModel):
    """Товар в корзине: имени и цены хватает для строки.

    Цены может не быть: товар без предпосчитанных вариантов её не
    имеет (ADR-0007), а в корзину кладут и такой.
    """

    id: int
    name: str
    price: int | None
    url: str
    photo: str
    category: str


class ProductSummaries(pydantic.BaseModel):
    items: list[ProductSummary]


class SummariesQuery(pydantic.BaseModel):
    ids: Annotated[
        str, pydantic.Field(pattern=IDS_PATTERN, max_length=MAX_IDS_LENGTH)
    ]

    @pydantic.field_validator("ids")
    @classmethod
    def _within_limit(cls, value: str) -> str:
        if len([chunk for chunk in value.split(",") if chunk]) > MAX_ITEMS:
            message = f"Не больше {MAX_ITEMS} товаров в подборке."
            raise ValueError(message)
        return value


class ConfigurationInput(pydantic.BaseModel):
    """Как покупатель настроил это зеркало, кладя его в заявку.

    Здесь только присланное: габариты и выбранные значения. Цены в
    заявке нет намеренно — её ставит сервер, пересчитывая это же
    теми же тарифами. Число из браузера доказательством в споре
    о цене не было бы (ADR-0005, ADR-0009).
    """

    # Границы здесь шире, чем у расчёта, намеренно: за не тем числом
    # в поле размера стоят настоящие имя и телефон, и разбор, отвергший
    # заявку целиком, потерял бы их. Что расчёт возьмёт, а что нет,
    # решает `catalog.quoting` — и негодное становится снимком без
    # цены, а не 422-м. Здесь остаётся защита хранилища: столько
    # цифр не бывает и у опечатки
    width_mm: StoredSide
    height_mm: StoredSide
    values: Annotated[
        list[int], pydantic.Field(max_length=MAX_STORED_VALUES)
    ] = []


class ItemInput(pydantic.BaseModel):
    """Позиция подборки: товар и то, каким его настроили.

    Подборка присылает не список id, а список позиций: конфигурация
    у зеркала своя, и без неё заявка из двух зеркал разных размеров
    запомнила бы одно (ADR-0009).

    Конфигурации может не быть вовсе: калькулятор есть не у всякого
    товара, и настраивать покупателю там нечего.

    Пожелание же бывает у любой позиции, в том числе у товара без
    калькулятора: оно свободный текст и в расчёт не идёт (тикет 15).
    """

    product: Annotated[int, pydantic.Field(ge=1)]
    configuration: ConfigurationInput | None = None
    # Потолок тот же, что у поля модели, и здесь он отвергает заявку
    # целиком — не так, как поступлено с размером десятью строками
    # выше. Разница не в строгости, а в том, откуда берётся негодное
    # значение: не тот размер набирает настоящий покупатель с
    # настоящим телефоном, и отвергнутая заявка потеряла бы его.
    # Пожелания длиннее потолка форма не производит вовсе — его
    # режут и `maxlength` поля, и `shop.js`, — так что за такой
    # длиной стоит не опечатка, а обход формы, и терять с ним нечего
    wish: Annotated[
        str, Trimmed, pydantic.Field(max_length=MAX_WISH_LENGTH)
    ] = ""


class InquiryInput(pydantic.BaseModel):
    """Заявка с витрины; согласие обязательно — иначе не заявка."""

    name: Annotated[str, Trimmed, pydantic.Field(min_length=2, max_length=120)]
    phone: Annotated[str, Trimmed, pydantic.Field(pattern=PHONE_PATTERN)]
    email: Annotated[
        str,
        Trimmed,
        pydantic.Field(default="", pattern=EMAIL_PATTERN, max_length=254),
    ] = ""
    comment: Annotated[str, Trimmed, pydantic.Field(max_length=2000)] = ""
    # Значения берутся из модели: список источников живёт в одном месте
    source: Inquiry.Source = Inquiry.Source.HOME
    # Literal[True] вместо bool: снятый чекбокс — ошибка валидации,
    # а не заявка без согласия
    consent: Literal[True]
    # Потолок тот же, что у подборки: список длиннее описывает не
    # заявку, а попытку нагрузить сервер
    items: Annotated[
        list[ItemInput], pydantic.Field(max_length=MAX_ITEMS)
    ] = []

    @pydantic.field_validator("phone")
    @classmethod
    def _callable_number(cls, value: str) -> str:
        if sum(char.isdigit() for char in value) < MIN_PHONE_DIGITS:
            message = "Телефон должен содержать номер, а не только знаки."
            raise ValueError(message)
        return value


class InquiryCreated(pydantic.BaseModel):
    id: int


def _published(ids: list[int]) -> tuple[dict[int, Product], list[int]]:
    """Опубликованные товары в порядке запроса плюс список пропавших.

    Одна выборка на оба эндпоинта: подборке пропавшие безразличны,
    заявке — нет, поэтому решает вызывающий, а не запрос.

    Отдаётся отображение, а не список: заявка идёт по присланным
    позициям и спрашивает товар по id. Список пришлось бы искать
    линейно, а совпадение по порядку тут и не выйдет — пропавшие
    товары из него уже вынуты.
    """
    unique = list(dict.fromkeys(ids))
    found = {
        product.pk: product
        for product in Product.objects.published()
        .filter(pk__in=unique)
        .select_related("category")
    }
    return (
        {pk: found[pk] for pk in unique if pk in found},
        [pk for pk in unique if pk not in found],
    )


def _summary(product: Product) -> ProductSummary:
    return ProductSummary(
        id=product.pk,
        name=product.name,
        price=product.price,
        url=reverse(
            "product",
            kwargs={
                "category_slug": product.category.slug,
                "slug": product.slug,
            },
        ),
        photo=product.photo_small.url if product.photo_small else "",
        category=product.category.name,
    )


class Snapshot(NamedTuple):
    """Расчёт позиции, каким он ложится в журнал: строка и цена.

    Цены может не быть при самой конфигурации, и почему — сказано
    в строке: сайт не называет цену ни за пределом производства, ни
    там, где считать нечего.
    """

    configuration: str
    calculated_price: int | None


NO_CALCULATION = Snapshot(configuration="", calculated_price=None)


def _snapshot(product: Product, sent: ConfigurationInput | None) -> Snapshot:
    """Расчёт позиции — пересчитанный здесь, а не принятый на слово.

    Считается тем же `catalog.quoting`, что и витрина: разойдись они,
    в заявке оказалась бы цена, которой карточка не показывала, — а
    спор о цене решается именно ею. Спрашивается он теперь на каждую
    позицию: у зеркала в ванную и у зеркала в прихожую свои размеры
    (ADR-0009).

    Не посчиталось — позиция всё равно остаётся позицией, а заявка
    принимается. Лид дороже снимка: заявку на личное пожелание
    менеджер должен получить, «чтобы не терять заказ, который сайт
    посчитать не умеет» (спека расчёта, история 32). Габариты
    покупателя остаются в снимке и в этом случае — гадать о них
    менеджеру не приходится.
    """
    if sent is None:
        return NO_CALCULATION
    try:
        quote = quoting.quote(
            product_id=product.pk,
            width_mm=sent.width_mm,
            height_mm=sent.height_mm,
            value_ids=sent.values,
        )
    except quoting.UncalculableError:
        return Snapshot(
            quoting.unrecognised_label(sent.width_mm, sent.height_mm), None
        )
    return Snapshot(quote.label, quote.total)


def _item(inquiry: Inquiry, product: Product, sent: ItemInput) -> InquiryItem:
    """Позиция снимком: название, цена «от», конфигурация и пожелание.

    Цену конфигурации ставит сервер — как и редакцию согласия.

    Пожелание же принимается как есть: пересчитывать в нём нечего, оно
    и есть та часть заявки, которую сайт посчитать не умеет (тикет 15).
    """
    snapshot = _snapshot(product, sent.configuration)
    return InquiryItem(
        inquiry=inquiry,
        product=product,
        product_name=product.name,
        product_price=product.price,
        configuration=snapshot.configuration,
        calculated_price=snapshot.calculated_price,
        wish=sent.wish,
    )


class ProductSummariesController(Controller[PydanticSerializer]):
    """Товары подборки по их id — цены и названия берутся с сервера."""

    def get(self, parsed_query: Query[SummariesQuery]) -> ProductSummaries:
        # Исчезнувшие товары просто выпадают из подборки
        products, _missing = _published(parse_ids(parsed_query.ids))
        return ProductSummaries(
            items=[_summary(item) for item in products.values()]
        )


@csrf_protect_json
class InquiryController(Controller[PydanticSerializer]):
    """Приём заявки: журнал в админке и уведомление владельцу."""

    responses: ClassVar = [*csrf_protect_json.responses]
    # Лимита на частоту заявок здесь нет: dmr считает по REMOTE_ADDR,
    # а за обратным прокси это один счётчик на всех посетителей — сайт
    # молча перестал бы принимать заявки. Антифлуд нужен вместе
    # с доверенным прокси и общим кэшем, отдельной задачей

    @modify(
        status_code=HTTPStatus.CREATED,
        extra_responses=[UNPROCESSABLE],
    )
    def post(self, parsed_body: Body[InquiryInput]) -> InquiryCreated:
        products = self._products(parsed_body.items)
        inquiry = self._store(parsed_body, products)
        notify(inquiry)
        return InquiryCreated(id=inquiry.pk)

    def _products(self, items: list[ItemInput]) -> dict[int, Product]:
        products, missing = _published([item.product for item in items])
        if missing:
            reject(
                self,
                "Товара из подборки больше нет в каталоге, обновите страницу.",
            )
        return products

    def _store(
        self, payload: InquiryInput, products: dict[int, Product]
    ) -> Inquiry:
        with transaction.atomic():
            # Поля уже обрезаны валидацией (Trimmed)
            inquiry = Inquiry.objects.create(
                name=payload.name,
                phone=payload.phone,
                email=payload.email,
                comment=payload.comment,
                source=payload.source,
                consent=payload.consent,
                consent_version=PRIVACY_VERSION,
            )
            # Позиция на каждую присланную, а не на каждый товар: одно
            # зеркало в двух размерах — две позиции (ADR-0009)
            InquiryItem.objects.bulk_create(
                _item(inquiry, products[sent.product], sent)
                for sent in payload.items
            )
        return inquiry
