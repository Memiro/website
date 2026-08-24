from decimal import Decimal
from http import HTTPStatus
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from django.test import Client
from pytest_django.fixtures import Settings

if TYPE_CHECKING:
    # Тип ответа тестового клиента живёт только в стабах django-stubs
    from django.test.client import (
        _MonkeyPatchedWSGIResponse as TestResponse,
    )

from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    PricingSettings,
    Product,
    ProductAttribute,
)
from memiro.inquiries.models import Inquiry
from memiro.inquiries.notifications import inquiry_message
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
def test_inquiry_of_a_product_without_a_price_says_so(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """Товару без вариантов цены не завели (ADR-0007).

    Менеджеру важно прочитать это в заявке, а не «от None ₽».
    """
    settings.INQUIRY_NOTIFIER = RECORDING
    Product.objects.filter(pk=products[0].pk).update(price=None)

    post_inquiry(client, items=[products[0].pk])
    message = inquiry_message(Inquiry.objects.get())

    assert "Halo Moon, цена не рассчитана" in message
    assert "None" not in message


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


# --- Заявка с расчётом (тикет 21) -----------------------------------

# Условные тарифы: полотно 4 000 ₽/м², подогрев 3 500 ₽/шт
GLASS_RATE = Decimal(4000)
HEATING_RATE = Decimal(3500)
# Зеркало 800 × 600 — 0,48 м²: 1 920 ₽ полотна, с подогревом 5 420 ₽,
# итог округляется вверх до сотни. Имена намеренно свои: у фикстуры
# `shop` в test_price_endpoint.py другие тарифы и другие числа
SILVER_TOTAL = 2000
SILVER_WITH_HEATING = 5500
# Предел производства: длинная сторона до 2 500 мм, короткая до 1 500
MAX_LONG_SIDE_MM = 2500
MAX_SHORT_SIDE_MM = 1500


@pytest.fixture
def calculable(db: None) -> SimpleNamespace:
    """Зеркало в считаемом наборе: полотно и подогрев меняет покупатель."""
    PricingSettings.objects.create(
        max_long_side_mm=MAX_LONG_SIDE_MM,
        max_short_side_mm=MAX_SHORT_SIDE_MM,
    )
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    blade = Attribute.objects.create(
        category=category,
        name="Тип полотна",
        slug="tip-polotna",
        is_customer_editable=True,
    )
    silver = AttributeValue.objects.create(
        attribute=blade,
        value="Серебро",
        unit=AttributeValue.Unit.SQUARE_METER,
        rate=GLASS_RATE,
    )
    heating_attribute = Attribute.objects.create(
        category=category,
        name="Подогрев",
        slug="podogrev",
        is_customer_editable=True,
        order=1,
    )
    heating = AttributeValue.objects.create(
        attribute=heating_attribute,
        value="Есть",
        unit=AttributeValue.Unit.PIECE,
        rate=HEATING_RATE,
    )
    # Умолчание товара: бесплатное «нет» — покупатель его и заменяет
    no_heating = AttributeValue.objects.create(
        attribute=heating_attribute, value="Нет", order=1
    )
    product = Product.objects.create(
        category=category,
        name="Halo Moon",
        slug="halo-moon",
        is_published=True,
    )
    ProductAttribute.objects.create(
        product=product, attribute=blade, value_option=silver
    )
    ProductAttribute.objects.create(
        product=product, attribute=heating_attribute, value_option=no_heating
    )
    return SimpleNamespace(
        product=product,
        silver=silver,
        heating=heating,
        no_heating=no_heating,
    )


def post_calculated(
    client: Client,
    calculable: SimpleNamespace,
    *,
    width_mm: int = 800,
    height_mm: int = 600,
    values: list[int] | None = None,
    **overrides: object,
) -> TestResponse:
    return post_inquiry(
        client,
        source="product",
        items=[calculable.product.pk],
        configuration={
            "width_mm": width_mm,
            "height_mm": height_mm,
            "values": [calculable.silver.pk] if values is None else values,
        },
        **overrides,
    )


@pytest.mark.django_db
def test_calculated_inquiry_keeps_configuration_and_total(
    client: Client, calculable: SimpleNamespace, settings: Settings
) -> None:
    """Заявка с расчётом сохраняет конфигурацию и посчитанный итог."""
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_calculated(
        client,
        calculable,
        values=[calculable.silver.pk, calculable.heating.pk],
    )

    assert response.status_code == HTTPStatus.CREATED
    inquiry = Inquiry.objects.get()
    assert inquiry.configuration == (
        "800 × 600 мм; Тип полотна: Серебро; Подогрев: Есть"
    )
    assert inquiry.calculated_price == SILVER_WITH_HEATING


@pytest.mark.django_db
def test_the_stored_price_is_the_servers_own(
    client: Client, calculable: SimpleNamespace, settings: Settings
) -> None:
    """В журнале — ровно то число, что витрина и показывала.

    Заявка присылает конфигурацию, а не цену. Сверяется снимок не с
    константой, а с ответом эндпоинта расчёта на ту же конфигурацию:
    разойдись эти двое, спор о цене решался бы снимком, которого
    покупатель не видел.
    """
    settings.INQUIRY_NOTIFIER = RECORDING
    shown = client.get(
        "/api/price",
        {
            "product": calculable.product.pk,
            "width_mm": 800,
            "height_mm": 600,
            "values": f"{calculable.silver.pk},{calculable.heating.pk}",
        },
    ).json()["total"]

    post_calculated(
        client,
        calculable,
        values=[calculable.silver.pk, calculable.heating.pk],
    )

    assert shown == SILVER_WITH_HEATING
    assert Inquiry.objects.get().calculated_price == shown


@pytest.mark.django_db
def test_a_size_beyond_the_limit_is_kept_without_a_price(
    client: Client, calculable: SimpleNamespace, settings: Settings
) -> None:
    """Личное пожелание: размер менеджеру нужен, цены у него нет.

    Сайт такого размера не считает и не называет цену — но чего именно
    хотел покупатель, менеджер должен прочитать в заявке.
    """
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_calculated(
        client, calculable, width_mm=MAX_LONG_SIDE_MM + 100, height_mm=400
    )

    assert response.status_code == HTTPStatus.CREATED
    inquiry = Inquiry.objects.get()
    assert inquiry.configuration.startswith(f"{MAX_LONG_SIDE_MM + 100} × 400")
    assert inquiry.calculated_price is None


@pytest.mark.django_db
def test_an_unrecognised_configuration_does_not_cost_the_lead(
    client: Client, calculable: SimpleNamespace, settings: Settings
) -> None:
    """Не посчиталось — заявка всё равно принимается.

    Значение исчезло из справочника, товар вышел из считаемого
    набора: цены у такого снимка нет, но заявку на личное пожелание
    менеджер должен получить, а не потерять (спека расчёта, 32).
    Габариты покупателя в снимке остаются.
    """
    settings.INQUIRY_NOTIFIER = RECORDING
    alien = AttributeValue.objects.create(
        attribute=Attribute.objects.create(
            category=Category.objects.create(name="Двери", slug="dveri"),
            name="Стекло",
            slug="steklo",
            is_customer_editable=True,
        ),
        value="Матовое",
    )

    response = post_calculated(client, calculable, values=[alien.pk])

    assert response.status_code == HTTPStatus.CREATED
    inquiry = Inquiry.objects.get()
    assert (
        inquiry.configuration == "800 × 600 мм; конфигурацию сайт не распознал"
    )
    assert inquiry.calculated_price is None


@pytest.mark.django_db
def test_a_configuration_without_a_single_product_keeps_the_sizes(
    client: Client, settings: Settings
) -> None:
    """Расчёт без единственного изделия не о чем — но заявка проходит."""
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(
        client,
        source="product",
        items=[],
        configuration={"width_mm": 800, "height_mm": 600, "values": []},
    )

    assert response.status_code == HTTPStatus.CREATED
    assert Inquiry.objects.get().configuration.startswith("800 × 600 мм")


@pytest.mark.django_db
def test_the_snapshot_says_why_there_is_no_price(
    client: Client, calculable: SimpleNamespace, settings: Settings
) -> None:
    """«Цены нет» у разных причин читается по-разному.

    За пределом производства сайт не называет цену никому, а
    неcчитаемую конфигурацию не взял бы и калькулятор: разговор
    с покупателем у них разный, и менеджер должен видеть, какой.
    """
    settings.INQUIRY_NOTIFIER = RECORDING

    post_calculated(
        client, calculable, width_mm=MAX_LONG_SIDE_MM + 100, height_mm=400
    )

    assert Inquiry.objects.get().configuration.endswith(
        "размер за пределом производства"
    )


@pytest.mark.django_db
def test_an_inquiry_without_a_calculation_is_unchanged(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """Заявка из корзины и свободной формой работает как раньше."""
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(client, items=[p.pk for p in products])

    assert response.status_code == HTTPStatus.CREATED
    inquiry = Inquiry.objects.get()
    assert inquiry.configuration == ""
    assert inquiry.calculated_price is None
    assert "Расчёт:" not in inquiry_message(inquiry)


@pytest.mark.django_db
def test_the_manager_reads_the_calculation_in_the_notification(
    client: Client, calculable: SimpleNamespace, settings: Settings
) -> None:
    """Конфигурация и цена уезжают менеджеру вместе с контактами."""
    settings.INQUIRY_NOTIFIER = RECORDING

    post_calculated(client, calculable)
    message = inquiry_message(Inquiry.objects.get())

    assert "Расчёт: 800 × 600 мм; Тип полотна: Серебро" in message
    assert f"Показанная цена: {SILVER_TOTAL} ₽" in message


@pytest.mark.django_db
def test_the_manager_reads_the_calculation_in_the_journal(
    client: Client,
    admin_client: Client,
    calculable: SimpleNamespace,
    settings: Settings,
) -> None:
    """Конфигурация и цена видны в списке заявок, без открытия товара."""
    settings.INQUIRY_NOTIFIER = RECORDING
    post_calculated(client, calculable)

    page = admin_client.get("/admin/inquiries/inquiry/").content.decode()

    assert "800 × 600 мм; Тип полотна: Серебро" in page
    assert "2\u202f000 ₽" in page


@pytest.mark.django_db
def test_an_absurd_size_does_not_cost_the_lead(
    client: Client, calculable: SimpleNamespace, settings: Settings
) -> None:
    """Опечатка в поле размера не отменяет заявку.

    За не тем числом стоят настоящие имя и телефон. Расчёт такого
    размера не берёт — но теряется снимок, а не заказ (спека
    расчёта, 32).
    """
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_calculated(client, calculable, width_mm=900_000)

    assert response.status_code == HTTPStatus.CREATED
    inquiry = Inquiry.objects.get()
    assert inquiry.configuration.endswith("конфигурацию сайт не распознал")
    assert inquiry.calculated_price is None


@pytest.mark.django_db
def test_a_cart_inquiry_carries_no_configuration(
    client: Client, calculable: SimpleNamespace, settings: Settings
) -> None:
    """Конфигурации нет у заявки из корзины — и решает это сервер.

    Браузер её оттуда и не шлёт, но снимок ставит не он (CONTEXT.md,
    «Расчёт в заявке»).
    """
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(
        client,
        source="cart",
        items=[calculable.product.pk],
        configuration={"width_mm": 800, "height_mm": 600, "values": []},
    )

    assert response.status_code == HTTPStatus.CREATED
    assert Inquiry.objects.get().configuration == ""
