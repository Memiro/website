from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.test import Client
from pytest_django.fixtures import Settings

from memiro.catalog.formatting import rub
from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    Product,
)
from memiro.inquiries.limits import MAX_ITEMS, MAX_WISH_LENGTH
from memiro.inquiries.models import Inquiry, InquiryItem
from memiro.inquiries.notifications import inquiry_message
from tests.inquiries import (
    MAX_LONG_SIDE_MM,
    SILVER_TOTAL,
    SILVER_WITH_HEATING,
    item,
    payload,
    post_calculated,
    post_inquiry,
)
from tests.notifiers import RecordingNotifier

if TYPE_CHECKING:
    from types import SimpleNamespace

# Цена «от» первого зеркала фикстуры: её снимок читают несколько тестов
HALO_MOON_PRICE = 11795

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
            ("Halo Moon", "halo-moon", HALO_MOON_PRICE),
            ("View Match", "view-match", 8300),
        )
    ]


@pytest.mark.django_db
def test_inquiry_is_stored_with_cart_items(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """Заявка по подборке попадает в журнал вместе с составом."""
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(client, items=[item(p) for p in products])

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
    """Эндпоинт принимает заявку об одном товаре.

    Источник «карточка товара» витрина не шлёт с тикета 07, но
    контракт приёма его помнит: так пришли старые заявки, и
    переписывать историю нельзя.
    """
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(
        client, source="product", items=[item(products[0])], comment=""
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

    post_inquiry(client, items=[item(products[0])])
    message = inquiry_message(Inquiry.objects.get())

    assert "Halo Moon, цена не рассчитана" in message
    assert "None" not in message


@pytest.mark.django_db
def test_inquiry_notifies_owner(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """POST триггерит уведомление владельцу."""
    settings.INQUIRY_NOTIFIER = RECORDING

    post_inquiry(client, items=[item(products[0])])

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

    response = post_inquiry(client, items=[item(hidden), item(products[1])])

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
    stored = InquiryItem.objects.get()
    assert stored.configuration == (
        "800 × 600 мм; Тип полотна: Серебро; Подогрев: Есть"
    )
    assert stored.calculated_price == SILVER_WITH_HEATING


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
    assert InquiryItem.objects.get().calculated_price == shown


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
    stored = InquiryItem.objects.get()
    assert stored.configuration.startswith(f"{MAX_LONG_SIDE_MM + 100} × 400")
    assert stored.calculated_price is None


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
    stored = InquiryItem.objects.get()
    assert (
        stored.configuration == "800 × 600 мм; конфигурацию сайт не распознал"
    )
    assert stored.calculated_price is None


@pytest.mark.django_db
def test_a_free_form_inquiry_carries_no_configuration(
    client: Client, settings: Settings
) -> None:
    """Заявке свободной формой конфигурация не нужна вовсе.

    У неё и товара нет — приложить настроенное не к чему, и ей
    остаётся комментарий (ADR-0009).
    """
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(client, source="home", items=[])

    assert response.status_code == HTTPStatus.CREATED
    assert not InquiryItem.objects.exists()


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

    assert InquiryItem.objects.get().configuration.endswith(
        "размер за пределом производства"
    )


@pytest.mark.django_db
def test_an_inquiry_without_a_calculation_is_unchanged(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """Заявка по подборке и свободной формой работает как раньше."""
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(client, items=[item(p) for p in products])

    assert response.status_code == HTTPStatus.CREATED
    inquiry = Inquiry.objects.get()
    assert [stored.configuration for stored in inquiry.items.all()] == ["", ""]
    assert all(
        stored.calculated_price is None for stored in inquiry.items.all()
    )
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
    # Число разбито тем же фильтром, что и на витрине: заявка читается
    # одинаково и в письме, и в журнале
    assert f"Показанная цена: {rub(SILVER_TOTAL)} ₽" in message


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
    assert f"{rub(SILVER_TOTAL)} ₽" in page


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
    stored = InquiryItem.objects.get()
    assert stored.configuration.endswith("конфигурацию сайт не распознал")
    assert stored.calculated_price is None


@pytest.mark.django_db
def test_two_mirrors_of_different_sizes_arrive_whole(
    client: Client, calculable: SimpleNamespace, settings: Settings
) -> None:
    """Ради этого случая поля и переезжали на позицию (ADR-0009).

    Зеркало в ванную и зеркало в прихожую — разные размеры, разные
    цены. Одно поле на заявку запомнило бы одну конфигурацию из
    двух, и менеджер изготовил бы не то.
    """
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(
        client,
        items=[
            item(
                calculable.product,
                width_mm=800,
                height_mm=600,
                values=[calculable.silver.pk],
            ),
            item(
                calculable.product,
                width_mm=800,
                height_mm=600,
                values=[calculable.silver.pk, calculable.heating.pk],
            ),
        ],
    )

    assert response.status_code == HTTPStatus.CREATED
    stored = list(Inquiry.objects.get().items.all())
    assert [row.calculated_price for row in stored] == [
        SILVER_TOTAL,
        SILVER_WITH_HEATING,
    ]
    assert stored[0].configuration == "800 × 600 мм; Тип полотна: Серебро"
    assert stored[1].configuration.endswith("Подогрев: Есть")


@pytest.mark.django_db
def test_a_position_without_a_calculator_is_still_a_position(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """Товару без калькулятора настраивать нечего — но он в заявке.

    Конфигурации у такой позиции нет вовсе, и это не пробел: цену
    ему называет менеджер (ADR-0009).
    """
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(client, items=[item(products[0])])

    assert response.status_code == HTTPStatus.CREATED
    stored = InquiryItem.objects.get()
    assert stored.configuration == ""
    assert stored.calculated_price is None
    assert stored.product_price == HALO_MOON_PRICE


@pytest.mark.django_db
def test_more_positions_than_allowed_are_rejected(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """Потолок подборки считает позиции, а не товары (тикет 14).

    Переезд конфигурации превратил список id в список позиций —
    ограничение должно было переехать вместе с ним, иначе браузер
    прислал бы сколько угодно.
    """
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(
        client, items=[item(products[0])] * (MAX_ITEMS + 1)
    )

    # 400, как всякая невалидная форма запроса: список длиннее
    # потолка разбор не проходит вовсе
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert not Inquiry.objects.exists()


@pytest.mark.django_db
def test_the_manager_reads_each_configuration_in_the_notification(
    client: Client, calculable: SimpleNamespace, settings: Settings
) -> None:
    """Конфигурация печатается у своего зеркала, а не над составом."""
    settings.INQUIRY_NOTIFIER = RECORDING

    post_inquiry(
        client,
        items=[
            item(
                calculable.product,
                width_mm=800,
                height_mm=600,
                values=[calculable.silver.pk],
            ),
            item(
                calculable.product,
                width_mm=1200,
                height_mm=400,
                values=[calculable.silver.pk, calculable.heating.pk],
            ),
        ],
    )
    inquiry = Inquiry.objects.get()
    message = inquiry_message(inquiry)

    assert "Расчёт: 800 × 600 мм" in message
    assert "Расчёт: 1200 × 400 мм" in message
    # По строке цены на зеркало — ни одной над составом
    assert message.count("Показанная цена:") == len(inquiry.items.all())


@pytest.mark.django_db
def test_the_admin_shows_the_configuration_inside_the_items(
    client: Client,
    admin_client: Client,
    calculable: SimpleNamespace,
    settings: Settings,
) -> None:
    """В карточке заявки конфигурация стоит в составе, а не над ним.

    Над составом ей места нет: заявка из двух зеркал показала бы там
    одну конфигурацию из двух (ADR-0009).
    """
    settings.INQUIRY_NOTIFIER = RECORDING
    post_calculated(client, calculable)
    inquiry = Inquiry.objects.get()

    page = admin_client.get(
        f"/admin/inquiries/inquiry/{inquiry.pk}/change/"
    ).content.decode()

    assert "800 × 600 мм; Тип полотна: Серебро" in page
    # Поле заявки исчезло вместе с полем модели: второй правде о цене
    # взяться неоткуда
    assert 'name="configuration"' not in page


@pytest.mark.django_db
def test_each_mirror_carries_its_own_wish(
    client: Client, calculable: SimpleNamespace, settings: Settings
) -> None:
    """Ради этого случая пожелание и живёт у позиции (тикет 15).

    У зеркала в ванную и у зеркала в прихожую хотелки разные, и
    сложенные в один комментарий они заставили бы менеджера
    разбирать, что к чему относится.
    """
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(
        client,
        items=[
            item(
                calculable.product,
                wish="Второй выключатель слева",
                width_mm=800,
                height_mm=600,
                values=[calculable.silver.pk],
            ),
            item(
                calculable.product,
                wish="Вырез под розетку",
                width_mm=1200,
                height_mm=400,
                values=[calculable.silver.pk],
            ),
        ],
    )

    assert response.status_code == HTTPStatus.CREATED
    assert [row.wish for row in Inquiry.objects.get().items.all()] == [
        "Второй выключатель слева",
        "Вырез под розетку",
    ]


@pytest.mark.django_db
def test_a_wish_is_not_a_configuration(
    client: Client, calculable: SimpleNamespace, settings: Settings
) -> None:
    """Пожелание в расчёт не идёт: ни в строку, ни в цену.

    Тем личное пожелание и отличается от выбора из справочника — сайт
    его посчитать не умеет, и притворяться обратным не должен.
    """
    settings.INQUIRY_NOTIFIER = RECORDING

    post_inquiry(
        client,
        items=[
            item(
                calculable.product,
                wish="Второй выключатель слева",
                width_mm=800,
                height_mm=600,
                values=[calculable.silver.pk],
            )
        ],
    )

    stored = InquiryItem.objects.get()
    assert stored.configuration == "800 × 600 мм; Тип полотна: Серебро"
    assert stored.calculated_price == SILVER_TOTAL


@pytest.mark.django_db
def test_a_wish_needs_no_calculator(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """Сказать словами покупатель вправе и там, где расчёта нет.

    Калькулятор есть не у всякого товара, а пожелание к такому зеркалу
    менеджеру нужно тем более: цену ему называть по нему.
    """
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(
        client, items=[item(products[0], wish="Скруглить углы")]
    )

    assert response.status_code == HTTPStatus.CREATED
    stored = InquiryItem.objects.get()
    assert stored.wish == "Скруглить углы"
    assert stored.configuration == ""


@pytest.mark.django_db
def test_a_wish_longer_than_the_limit_is_refused(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """Свободный текст без потолка — нагрузка на журнал, не пожелание.

    Браузер такой длины не выпустит: `maxlength` полей приезжает из
    того же `limits.py`. Отвергается запрос целиком, как и список
    позиций сверх потолка, — обходят форму не опечаткой.
    """
    settings.INQUIRY_NOTIFIER = RECORDING

    response = post_inquiry(
        client,
        items=[item(products[0], wish="а" * (MAX_WISH_LENGTH + 1))],
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert not Inquiry.objects.exists()


@pytest.mark.django_db
def test_the_manager_reads_the_wish_under_its_position(
    client: Client, calculable: SimpleNamespace, settings: Settings
) -> None:
    """Пожелание печатается под своим зеркалом, а не над составом."""
    settings.INQUIRY_NOTIFIER = RECORDING

    post_inquiry(
        client,
        items=[
            item(
                calculable.product,
                wish="Второй выключатель слева",
                width_mm=800,
                height_mm=600,
                values=[calculable.silver.pk],
            ),
            item(calculable.product, wish="Вырез под розетку"),
        ],
    )
    lines = inquiry_message(Inquiry.objects.get()).splitlines()

    # Пожелание идёт следом за своим зеркалом — с расчётом между ними
    # у первой позиции и вплотную у второй, где расчёта не было
    assert lines.index("  Пожелание: Второй выключатель слева") < lines.index(
        "  Пожелание: Вырез под розетку"
    )
    assert lines.count("  Пожелание: Вырез под розетку") == 1


@pytest.mark.django_db
def test_a_multiline_wish_keeps_its_indent(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """Вторая строка пожелания не выдаёт себя за ещё одно зеркало.

    Позиции письма начинаются с тире у левого края; отступ — то
    единственное, чем строки одной позиции держатся вместе.
    """
    settings.INQUIRY_NOTIFIER = RECORDING

    post_inquiry(
        client,
        items=[item(products[0], wish="Второй выключатель\nи вырез снизу")],
    )
    message = inquiry_message(Inquiry.objects.get())

    assert "  Пожелание: Второй выключатель" in message
    assert "\n  и вырез снизу" in message


@pytest.mark.django_db
def test_an_inquiry_without_a_wish_says_nothing_about_it(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """Пустое пожелание в письме не занимает строки."""
    settings.INQUIRY_NOTIFIER = RECORDING

    post_inquiry(client, items=[item(products[0])])

    assert "Пожелание" not in inquiry_message(Inquiry.objects.get())


@pytest.mark.django_db
def test_the_admin_shows_the_wish_inside_the_items(
    client: Client,
    admin_client: Client,
    products: list[Product],
    settings: Settings,
) -> None:
    """Пожелание видно в составе заявки — и видно как текст.

    Покупатель пишет свободным текстом, и разметка в нём остаётся
    разметкой на экране, а не в браузере менеджера.
    """
    settings.INQUIRY_NOTIFIER = RECORDING
    post_inquiry(client, items=[item(products[0], wish="<b>срочно</b>")])
    inquiry = Inquiry.objects.get()

    page = admin_client.get(
        f"/admin/inquiries/inquiry/{inquiry.pk}/change/"
    ).content.decode()

    assert "&lt;b&gt;срочно&lt;/b&gt;" in page
    assert "<b>срочно</b>" not in page


@pytest.mark.django_db
def test_the_admin_keeps_the_paragraphs_of_the_wish(
    client: Client,
    admin_client: Client,
    products: list[Product],
    settings: Settings,
) -> None:
    """Абзацы пожелания видны и в журнале, а не склеиваются в строку.

    Читателей у заявки двое — письмо и админка, — и текст покупателя
    они показывают одинаково.
    """
    settings.INQUIRY_NOTIFIER = RECORDING
    post_inquiry(client, items=[item(products[0], wish="Первое\nВторое")])
    inquiry = Inquiry.objects.get()

    page = admin_client.get(
        f"/admin/inquiries/inquiry/{inquiry.pk}/change/"
    ).content.decode()

    assert "Первое<br>Второе" in page


@pytest.mark.django_db
def test_a_wish_keeps_the_paragraphs_of_the_buyer(
    client: Client, products: list[Product], settings: Settings
) -> None:
    """Абзацы ставил покупатель — письмо его текст не правит."""
    settings.INQUIRY_NOTIFIER = RECORDING

    post_inquiry(
        client,
        items=[item(products[0], wish="Первое\n\nВторое")],
    )

    assert "  Пожелание: Первое\n\n  Второе" in inquiry_message(
        Inquiry.objects.get()
    )


@pytest.mark.django_db
def test_a_hidden_price_still_sends_the_configuration(
    client: Client, calculable: SimpleNamespace, settings: Settings
) -> None:
    """Погашенная цена отбирает число, а не ТЗ (тикет 16, ADR-0008).

    Ради этого конструктор и оставлен на карточке: менеджер получает
    размер и выбранные значения готовыми, а цену называет сам — и
    видит в снимке, почему её нет.
    """
    settings.INQUIRY_NOTIFIER = RECORDING
    calculable.product.hides_calculated_price = True
    calculable.product.save()

    response = post_calculated(
        client,
        calculable,
        values=[calculable.silver.pk, calculable.heating.pk],
    )

    assert response.status_code == HTTPStatus.CREATED
    stored = InquiryItem.objects.get()
    assert stored.calculated_price is None
    assert stored.configuration == (
        "800 × 600 мм; Тип полотна: Серебро; Подогрев: Есть; "
        "цену этого зеркала называет менеджер"
    )
