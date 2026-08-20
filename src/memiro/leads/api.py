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
from dmr.throttling import Rate, SyncThrottle

from memiro.api.csrf import csrf_protect_json
from memiro.catalog.models import Product
from memiro.leads.models import Lead, LeadItem
from memiro.leads.notifications import notify

# Телефон принимаем в любом человеческом написании: цифры, скобки,
# плюс, пробелы и дефисы. Нормализацией занимается менеджер, не сайт
PHONE_PATTERN = r"^[\d\s()+\-]{6,32}$"
# ...но дозвониться по одним скобкам нельзя: цифр должно быть достаточно
# для номера без кода страны
MIN_PHONE_DIGITS = 7
# Пустая строка — «не указан»; иначе минимальная форма адреса
EMAIL_PATTERN = r"^$|^[^@\s]+@[^@\s]+\.[^@\s]{2,}$"
# Список id через запятую либо пусто: «пустая корзина» — не ошибка
IDS_PATTERN = r"^(\d+(,\d+)*)?$"
# Потолок подборки: столько же товаров принимает и заявка
MAX_ITEMS = 100

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

    def parsed(self) -> list[int]:
        return [int(chunk) for chunk in self.ids.split(",") if chunk]

    @pydantic.field_validator("ids")
    @classmethod
    def _within_limit(cls, value: str) -> str:
        if len([chunk for chunk in value.split(",") if chunk]) > MAX_ITEMS:
            message = f"Не больше {MAX_ITEMS} товаров в подборке."
            raise ValueError(message)
        return value


class LeadInput(pydantic.BaseModel):
    """Заявка с витрины; согласие обязательно — иначе не заявка."""

    name: Annotated[str, Trimmed, pydantic.Field(min_length=2, max_length=120)]
    phone: Annotated[str, Trimmed, pydantic.Field(pattern=PHONE_PATTERN)]
    email: Annotated[
        str,
        Trimmed,
        pydantic.Field(default="", pattern=EMAIL_PATTERN, max_length=254),
    ] = ""
    comment: Annotated[str, Trimmed, pydantic.Field(max_length=2000)] = ""
    source: Literal["home", "product", "cart"] = "home"
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


class LeadCreated(pydantic.BaseModel):
    id: int


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
        ids = parsed_query.parsed()
        found = {
            product.pk: product
            for product in Product.objects.published()
            .filter(pk__in=ids)
            .select_related("category")
        }
        # Порядок задаёт клиент; исчезнувшие товары просто выпадают
        return ProductSummaries(
            items=[
                _summary(found[pk]) for pk in dict.fromkeys(ids) if pk in found
            ]
        )


@csrf_protect_json
class LeadController(Controller[PydanticSerializer]):
    """Приём заявки: журнал в админке и уведомление владельцу."""

    responses: ClassVar = [*csrf_protect_json.responses]
    # Заявка — редкое действие; лимит режет флуд в журнал и в Telegram.
    # Кэш локальный (на процесс) — общий появится вместе с прод-инфрой,
    # но и такой отбивает поток с одного адреса
    throttling: ClassVar = (
        SyncThrottle(max_requests=10, duration_in_seconds=Rate.hour),
    )
    throttling_allow_unsafe_cache = True

    @modify(
        status_code=HTTPStatus.CREATED,
        extra_responses=[UNPROCESSABLE],
    )
    def post(self, parsed_body: Body[LeadInput]) -> LeadCreated:
        products = self._products(parsed_body.items)
        lead = self._store(parsed_body, products)
        notify(lead)
        return LeadCreated(id=lead.pk)

    def _products(self, ids: list[int]) -> list[Product]:
        unique = list(dict.fromkeys(ids))
        found = {
            product.pk: product
            for product in Product.objects.published().filter(pk__in=unique)
        }
        missing = [pk for pk in unique if pk not in found]
        if missing:
            raise APIError(
                self.format_error(
                    "Товара из подборки больше нет в каталоге, "
                    "обновите страницу.",
                    error_type=ErrorType.user_msg,
                ),
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        return [found[pk] for pk in unique]

    def _store(self, payload: LeadInput, products: list[Product]) -> Lead:
        with transaction.atomic():
            # Поля уже обрезаны валидацией (Trimmed)
            lead = Lead.objects.create(
                name=payload.name,
                phone=payload.phone,
                email=payload.email,
                comment=payload.comment,
                source=payload.source,
                consent=payload.consent,
            )
            LeadItem.objects.bulk_create(
                LeadItem(
                    lead=lead,
                    product=product,
                    product_name=product.name,
                    product_price=product.price,
                )
                for product in products
            )
        return lead
