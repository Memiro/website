from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.test import Client
from pytest_django.fixtures import Settings

if TYPE_CHECKING:
    # Тип ответа тестового клиента живёт только в стабах django-stubs
    from django.test.client import (
        _MonkeyPatchedWSGIResponse as TestResponse,
    )

from memiro.catalog.models import Category, Product
from memiro.inquiries.models import Inquiry
from tests.notifiers import RecordingNotifier

RECORDING = "tests.notifiers.RecordingNotifier"
FAILING = "tests.notifiers.FailingNotifier"


@pytest.fixture(autouse=True)
def _clear_notifier() -> None:
    RecordingNotifier.sent.clear()


@pytest.fixture
def products(db: None) -> list[Product]:
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    return [
        Product.objects.create(
            category=category,
            name=name,
            slug=slug,
            price=price,
            is_published=True,
        )
        for name, slug, price in (
            ("Halo Moon", "halo-moon", 11795),
            ("View Match", "view-match", 8300),
        )
    ]


def payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "Анна",
        "phone": "+7 981 000-00-00",
        "email": "anna@example.com",
        "comment": "Нужен замер",
        "consent": True,
        "source": "cart",
        "items": [],
    }
    return body | overrides


def post_inquiry(client: Client, **overrides: object) -> TestResponse:
    return client.post(
        "/api/inquiries",
        data=payload(**overrides),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_inquiry_is_stored_with_cart_items(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """Заявка из корзины попадает в журнал вместе с составом."""
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(client, items=[p.pk for p in products])

    assert response.status_code == HTTPStatus.CREATED
    inquiry = Inquiry.objects.get(pk=response.json()["id"])
    assert inquiry.name == "Анна"
    assert inquiry.phone == "+7 981 000-00-00"
    assert inquiry.email == "anna@example.com"
    assert inquiry.comment == "Нужен замер"
    assert inquiry.consent is True
    assert inquiry.source == Inquiry.Source.CART
    assert [item.product_name for item in inquiry.items.all()] == [
        "Halo Moon",
        "View Match",
    ]
    assert [item.product_price for item in inquiry.items.all()] == [
        11795,
        8300,
    ]


@pytest.mark.django_db
def test_inquiry_from_product_page_needs_no_items(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """Заявка возможна и с карточки товара — одним товаром."""
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(
        client, source="product", items=[products[0].pk], comment=""
    )

    assert response.status_code == HTTPStatus.CREATED
    inquiry = Inquiry.objects.get()
    assert inquiry.source == Inquiry.Source.PRODUCT
    assert inquiry.items.count() == 1


@pytest.mark.django_db
def test_inquiry_notifies_owner(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """POST триггерит уведомление владельцу."""
    settings.INQUIRY_NOTIFIER = RECORDING

    post_inquiry(client, items=[products[0].pk])

    assert len(RecordingNotifier.sent) == 1
    assert RecordingNotifier.sent[0].pk == Inquiry.objects.get().pk


@pytest.mark.django_db
def test_inquiry_survives_broken_notifier(
    client: Client, settings: Settings
) -> None:
    """Упавший транспорт не отменяет заявку: она уже в журнале."""
    settings.INQUIRY_NOTIFIER = FAILING

    response = post_inquiry(client)

    assert response.status_code == HTTPStatus.CREATED
    assert Inquiry.objects.count() == 1


@pytest.mark.django_db
def test_inquiry_without_consent_is_rejected(
    client: Client, settings: Settings
) -> None:
    """Без чекбокса согласия заявка не принимается."""
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(client, consent=False)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert not Inquiry.objects.exists()
    assert not RecordingNotifier.sent


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalid",
    [
        {"phone": ""},
        {"phone": "12"},
        {"name": ""},
        {"email": "не-почта"},
    ],
)
@pytest.mark.usefixtures("db")
def test_invalid_inquiry_is_rejected(
    client: Client, invalid: dict[str, str], settings: Settings
) -> None:
    """Невалидные контакты отклоняются, журнал остаётся пустым."""
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(client, **invalid)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert not Inquiry.objects.exists()


@pytest.mark.django_db
def test_email_is_optional(client: Client, settings: Settings) -> None:
    """E-mail не обязателен: телефона менеджеру достаточно."""
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(client, email="")

    assert response.status_code == HTTPStatus.CREATED
    assert Inquiry.objects.get().email == ""


@pytest.mark.django_db
def test_unpublished_product_is_not_accepted(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """Снятый с публикации товар в состав заявки не попадает."""
    settings.INQUIRY_NOTIFIER = RECORDING
    hidden = products[0]
    hidden.is_published = False
    hidden.save()

    response = post_inquiry(client, items=[hidden.pk, products[1].pk])

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert not Inquiry.objects.exists()


@pytest.mark.django_db
def test_inquiry_survives_broken_notifier_setting(
    client: Client, settings: Settings
) -> None:
    """Опечатка в INQUIRY_NOTIFIER — не 500 на уже принятую заявку."""
    settings.INQUIRY_NOTIFIER = "tests.notifiers.NoSuchNotifier"

    response = post_inquiry(client)

    assert response.status_code == HTTPStatus.CREATED
    assert Inquiry.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalid",
    [
        # Скобки и дефисы без цифр — не номер
        {"phone": "-- () --"},
        # Пробелы обрезаются до проверки длины
        {"name": "   "},
    ],
)
@pytest.mark.usefixtures("db")
def test_unusable_contacts_are_rejected(
    client: Client, invalid: dict[str, str], settings: Settings
) -> None:
    """Заявка, по которой нельзя связаться, в журнал не попадает."""
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(client, **invalid)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert not Inquiry.objects.exists()


@pytest.mark.django_db
def test_inquiry_without_csrf_token_is_rejected(
    settings: Settings,
) -> None:
    """Чужая страница заявку не отправит: проверка CSRF на месте."""
    settings.INQUIRY_NOTIFIER = RECORDING
    strict = Client(enforce_csrf_checks=True)

    response = post_inquiry(strict)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response["Content-Type"].startswith("application/json")
    assert not Inquiry.objects.exists()


@pytest.mark.django_db
def test_inquiry_with_csrf_token_is_accepted(settings: Settings) -> None:
    """Форма витрины отдаёт токен — заявка проходит."""
    settings.INQUIRY_NOTIFIER = RECORDING
    strict = Client(enforce_csrf_checks=True)
    strict.get("/")

    response = strict.post(
        "/api/inquiries",
        data=payload(),
        content_type="application/json",
        headers={"x-csrftoken": strict.cookies["csrftoken"].value},
    )

    assert response.status_code == HTTPStatus.CREATED


@pytest.mark.django_db
def test_inquirys_endpoint_is_in_openapi_schema(client: Client) -> None:
    """Эндпоинт заявок отражён в OpenAPI-схеме."""
    schema = client.get("/api/openapi/schema.json").json()

    assert "post" in schema["paths"]["/api/inquiries"]
