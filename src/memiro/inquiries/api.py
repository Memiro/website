"""JSON-эндпоинты пути до заявки: подборка товаров и приём заявки."""

from __future__ import annotations

from http import HTTPStatus
from typing import Annotated, ClassVar, Literal

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
from memiro.catalog.quoting import MAX_VALUES, Side, UncalculableError
from memiro.inquiries.limits import MAX_ITEMS, MIN_PHONE_DIGITS
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


class ProductSummary(pydantic.BaseModel):
    """Товар в корзине и избранном: имени и цены хватает для строки.

    Цены может не быть: товар без предпосчитанных вариантов её не
    имеет (ADR-0007), а в корзину и избранное кладут и такой.
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
    """Что покупатель считал калькулятором, отправляя заявку.

    Здесь только присланное: габариты и выбранные значения. Цены в
    заявке нет намеренно — её ставит сервер, пересчитывая это же
    теми же тарифами. Число из браузера доказательством в споре
    о цене не было бы (тикет 21).
    """

    width_mm: Side
    height_mm: Side
    # Потолок — число органов управления, а не товаров подборки:
    # столько значений расчёт возьмёт и от эндпоинта цены
    values: Annotated[list[int], pydantic.Field(max_length=MAX_VALUES)] = []


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
    items: Annotated[list[int], pydantic.Field(max_length=MAX_ITEMS)] = []
    # Расчёт есть не у всякой заявки: из корзины, свободной формой и
    # с карточки вне считаемого набора он не приходит вовсе
    configuration: ConfigurationInput | None = None

    @pydantic.field_validator("phone")
    @classmethod
    def _callable_number(cls, value: str) -> str:
        if sum(char.isdigit() for char in value) < MIN_PHONE_DIGITS:
            message = "Телефон должен содержать номер, а не только знаки."
            raise ValueError(message)
        return value


class InquiryCreated(pydantic.BaseModel):
    id: int


def _published(ids: list[int]) -> tuple[list[Product], list[int]]:
    """Опубликованные товары в порядке запроса плюс список пропавших.

    Одна выборка на оба эндпоинта: подборке пропавшие безразличны,
    заявке — нет, поэтому решает вызывающий, а не запрос.
    """
    unique = list(dict.fromkeys(ids))
    found = {
        product.pk: product
        for product in Product.objects.published()
        .filter(pk__in=unique)
        .select_related("category")
    }
    return (
        [found[pk] for pk in unique if pk in found],
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


class ProductSummariesController(Controller[PydanticSerializer]):
    """Товары подборки по их id — цены и названия берутся с сервера."""

    def get(self, parsed_query: Query[SummariesQuery]) -> ProductSummaries:
        # Исчезнувшие товары просто выпадают из подборки
        products, _missing = _published(parse_ids(parsed_query.ids))
        return ProductSummaries(items=[_summary(item) for item in products])


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
        inquiry = self._store(
            parsed_body, products, self._quote(parsed_body, products)
        )
        notify(inquiry)
        return InquiryCreated(id=inquiry.pk)

    def _quote(
        self, payload: InquiryInput, products: list[Product]
    ) -> quoting.Quote | None:
        """Расчёт заявки — пересчитанный здесь, а не принятый на слово.

        Считается тем же `catalog.quoting`, что и витрина: разойдись
        они, в заявке оказалась бы цена, которой карточка не
        показывала, — а спор о цене решается именно ею.

        Расчёт бывает только у заявки об одном товаре: конфигурация
        без единственного изделия не о чем. Отвергнутая конфигурация
        (значение исчезло из справочника, товар вышел из считаемого
        набора) заявку отклоняет со словами про обновление страницы —
        принять её, молча выбросив расчёт, значило бы отдать менеджеру
        заявку без того, ради чего её отправляли.
        """
        if payload.configuration is None:
            return None
        if len(products) != 1:
            reject(self, quoting.UNCALCULABLE)
        try:
            return quoting.quote(
                product_id=products[0].pk,
                width_mm=payload.configuration.width_mm,
                height_mm=payload.configuration.height_mm,
                value_ids=payload.configuration.values,
            )
        except UncalculableError as refusal:
            reject(self, str(refusal))

    def _products(self, ids: list[int]) -> list[Product]:
        products, missing = _published(ids)
        if missing:
            reject(
                self,
                "Товара из подборки больше нет в каталоге, обновите страницу.",
            )
        return products

    def _store(
        self,
        payload: InquiryInput,
        products: list[Product],
        quote: quoting.Quote | None,
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
                # Снимок ставит сервер — как и редакцию согласия
                configuration=quote.label if quote else "",
                calculated_price=quote.total if quote else None,
            )
            InquiryItem.objects.bulk_create(
                InquiryItem(
                    inquiry=inquiry,
                    product=product,
                    product_name=product.name,
                    product_price=product.price,
                )
                for product in products
            )
        return inquiry
