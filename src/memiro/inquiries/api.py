"""JSON-эндпоинты пути до заявки: подборка товаров и приём заявки."""

from __future__ import annotations

from http import HTTPStatus
from typing import Annotated, ClassVar, Literal

import pydantic
from django.db import transaction
from django.urls import reverse
from dmr import APIError, Body, Controller, Query, ResponseSpec, modify
from dmr.errors import ErrorModel, ErrorType
from dmr.plugins.pydantic import PydanticSerializer

from memiro.api.csrf import csrf_protect_json
from memiro.catalog.models import Product
from memiro.inquiries.limits import MAX_ITEMS, MIN_PHONE_DIGITS
from memiro.inquiries.models import Inquiry, InquiryItem
from memiro.inquiries.notifications import notify
from memiro.legal.privacy import PRIVACY_VERSION

# Телефон принимаем в любом человеческом написании: цифры, скобки,
# плюс, пробелы и дефисы. Нормализацией занимается менеджер, не сайт
PHONE_PATTERN = r"^[\d\s()+\-]{6,32}$"
# Пустая строка — «не указан»; иначе минимальная форма адреса
EMAIL_PATTERN = r"^$|^[^@\s]+@[^@\s]+\.[^@\s]{2,}$"
# Список id через запятую либо пусто: «пустая корзина» — не ошибка
IDS_PATTERN = r"^(\d+(,\d+)*)?$"

# Обрезка пробелов до проверки длины: «   » — пустое имя, а не двухсимвольное
Trimmed = pydantic.StringConstraints(strip_whitespace=True)

UNPROCESSABLE = ResponseSpec(
    return_type=ErrorModel,
    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
)


class ProductSummary(pydantic.BaseModel):
    """Товар в корзине и избранном: имени и цены хватает для строки."""

    id: int
    name: str
    price: int
    url: str
    photo: str
    category: str


class ProductSummaries(pydantic.BaseModel):
    items: list[ProductSummary]


class SummariesQuery(pydantic.BaseModel):
    # Длины хватает на MAX_ITEMS девятизначных id с запятыми
    ids: Annotated[str, pydantic.Field(pattern=IDS_PATTERN, max_length=1000)]

    def parsed_ids(self) -> list[int]:
        return [int(chunk) for chunk in self.ids.split(",") if chunk]

    @pydantic.field_validator("ids")
    @classmethod
    def _within_limit(cls, value: str) -> str:
        if len([chunk for chunk in value.split(",") if chunk]) > MAX_ITEMS:
            message = f"Не больше {MAX_ITEMS} товаров в подборке."
            raise ValueError(message)
        return value


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
        products, _missing = _published(parsed_query.parsed_ids())
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
        inquiry = self._store(parsed_body, products)
        notify(inquiry)
        return InquiryCreated(id=inquiry.pk)

    def _products(self, ids: list[int]) -> list[Product]:
        products, missing = _published(ids)
        if missing:
            raise APIError(
                self.format_error(
                    "Товара из подборки больше нет в каталоге, "
                    "обновите страницу.",
                    error_type=ErrorType.user_msg,
                ),
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        return products

    def _store(
        self, payload: InquiryInput, products: list[Product]
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
