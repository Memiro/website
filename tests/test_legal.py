"""Юридическое соответствие, проверяемое по HTTP (тикет 10).

Шов тот же, что и у остальной витрины: что сайт отдал посетителю.
Ключевое здесь — «чего сайт НЕ отдал»: без согласия в ответе не должно
быть ни счётчика Метрики, ни обращений к иностранным сервисам.
"""

import re
from http import HTTPStatus

import pytest
from django.test import Client
from pytest_django.fixtures import Settings

from memiro.catalog.models import Category, Product
from memiro.inquiries.models import Inquiry
from memiro.legal import analytics_consent, checks, seller
from memiro.legal.privacy import PRIVACY_VERSION
from tests.sources import site_css

COUNTER = "12345678"

# Адреса, любое обращение к которым ломает локализацию ПД (23-ФЗ):
# шрифты, CDN и виджеты должны быть свои или российские
FOREIGN_HOSTS = (
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "googletagmanager.com",
    "google-analytics.com",
    "cdn.jsdelivr.net",
    "unpkg.com",
    "cdnjs.cloudflare.com",
)

PAGES = (
    "/",
    "/catalog/zerkala/",
    "/catalog/zerkala/halo-moon/",
    "/cart/",
    "/contacts/",
    "/privacy/",
)
# Страницы с формой заявки — там, где собираются персональные данные
# Карточка товара выбыла с тикетом 07: формы заявки на ней больше нет
FORM_PAGES = ("/", "/cart/")
# Страницы, показывающие цену: везде нужна оговорка про оферту
PRICE_PAGES = (
    "/",
    "/catalog/zerkala/",
    "/catalog/zerkala/halo-moon/",
    "/cart/",
)


@pytest.fixture
def products(db: None) -> list[Product]:
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    return [
        Product.objects.create(
            category=category,
            name="Halo Moon",
            slug="halo-moon",
            price=11795,
            is_published=True,
            # Популярное — чтобы на главной была лента с ценами
            is_popular=True,
        ),
    ]


@pytest.fixture
def _requisites(monkeypatch: pytest.MonkeyPatch) -> None:
    """Реквизиты, какими их однажды впишет владелец."""
    monkeypatch.setattr(
        seller,
        "SELLER",
        seller.Seller(
            name="ИП Иванов Иван Иванович",
            ogrn="323470000000001",
            inn="470000000001",
            address="197198, Санкт-Петербург, ул. Тележная, 37",
        ),
    )


@pytest.mark.django_db
def test_privacy_policy_is_published(client: Client) -> None:
    """Политика опубликована — отдельный состав ст. 13.11 КоАП."""
    response = client.get("/privacy/")
    content = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert "Политика обработки персональных данных" in content
    assert PRIVACY_VERSION in content
    # Разделы, без которых политика не политика
    assert "152-ФЗ" in content
    assert 'id="cookie"' in content
    assert 'id="consent"' in content


@pytest.mark.django_db
def test_policy_is_linked_from_footer(client: Client) -> None:
    content = client.get("/").content.decode()

    assert 'href="/privacy/"' in content


@pytest.mark.django_db
@pytest.mark.parametrize("url", FORM_PAGES)
@pytest.mark.usefixtures("products")
def test_consent_checkbox_links_to_the_policy(
    client: Client, url: str
) -> None:
    """Ст. 9 152-ФЗ: согласие предметно — текст должен быть доступен."""
    content = client.get(url).content.decode()

    consent_label = re.search(
        r'<label class="consent">.*?</label>', content, re.DOTALL
    )
    assert consent_label, "форма заявки без блока согласия"
    assert 'href="/privacy/#consent"' in consent_label.group()


@pytest.mark.django_db
def test_inquiry_records_the_consent_version(
    client: Client, settings: Settings
) -> None:
    """Доказательство согласия — с какой редакцией текста согласились."""
    settings.INQUIRY_NOTIFIER = "tests.notifiers.RecordingNotifier"

    response = client.post(
        "/api/inquiries",
        data={
            "name": "Анна",
            "phone": "+7 981 000-00-00",
            "consent": True,
            "items": [],
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CREATED
    inquiry = Inquiry.objects.get(pk=response.json()["id"])
    assert inquiry.consent is True
    assert inquiry.consent_version == PRIVACY_VERSION


@pytest.mark.django_db
def test_metrika_is_absent_until_consent(
    client: Client, settings: Settings
) -> None:
    """Счётчика нет в отдаче, пока посетитель не нажал «Принять»."""
    settings.YANDEX_METRIKA_ID = COUNTER

    content = client.get("/").content.decode()

    assert "mc.yandex.ru" not in content
    assert COUNTER not in content
    assert "data-cookie-banner" in content


@pytest.mark.django_db
def test_metrika_loads_after_consent(
    client: Client, settings: Settings
) -> None:
    settings.YANDEX_METRIKA_ID = COUNTER
    client.cookies[analytics_consent.COOKIE_NAME] = analytics_consent.ACCEPTED

    content = client.get("/").content.decode()

    assert "mc.yandex.ru/metrika/tag.js" in content
    assert f'ym({COUNTER}, "init"' in content
    # Выбор запомнен — переспрашивать нечего
    assert "data-cookie-banner" not in content


@pytest.mark.django_db
def test_declined_choice_is_remembered(
    client: Client, settings: Settings
) -> None:
    """«Отклонить» тоже ответ: баннер не возвращается, счётчика нет."""
    settings.YANDEX_METRIKA_ID = COUNTER
    client.cookies[analytics_consent.COOKIE_NAME] = analytics_consent.DECLINED

    content = client.get("/").content.decode()

    assert "data-cookie-banner" not in content
    assert "mc.yandex.ru" not in content


@pytest.mark.django_db
def test_no_banner_without_a_counter(client: Client) -> None:
    """Без аналитики спрашивать не о чем: остаются нужные cookie."""
    content = client.get("/").content.decode()

    assert "data-cookie-banner" not in content


@pytest.mark.django_db
def test_non_numeric_counter_is_ignored(
    client: Client, settings: Settings
) -> None:
    """Номер счётчика уезжает в тело <script> — мусор туда не попадёт."""
    settings.YANDEX_METRIKA_ID = 'x");alert(1);//'
    client.cookies[analytics_consent.COOKIE_NAME] = analytics_consent.ACCEPTED

    content = client.get("/").content.decode()

    assert "alert(1)" not in content
    assert "mc.yandex.ru" not in content


@pytest.mark.django_db
@pytest.mark.parametrize("url", PAGES)
@pytest.mark.usefixtures("products")
def test_pages_reach_no_foreign_services(client: Client, url: str) -> None:
    """Локализация ПД (23-ФЗ): шрифты свои, чужих CDN и виджетов нет."""
    content = client.get(url).content.decode()

    for host in FOREIGN_HOSTS:
        assert host not in content


def test_fonts_are_self_hosted() -> None:
    """Шрифты лежат в статике проекта, а не приезжают из Google.

    Единственный тест, читающий файл: HTTP-шов его не достаёт. Страница
    ссылается на `site.css`, браузер его загрузит, и `@import` на Google
    Fonts внутри стилей утёк бы мимо `test_pages_reach_no_foreign_services`
    — а это ровно та локализация ПД (23-ФЗ), которую тикет и защищает.
    """
    css = site_css().read_text(encoding="utf-8")

    assert "@font-face" in css
    for host in FOREIGN_HOSTS:
        assert host not in css


@pytest.mark.django_db
@pytest.mark.usefixtures("products", "_requisites")
@pytest.mark.parametrize("url", ["/", "/contacts/"])
def test_seller_requisites_are_published(client: Client, url: str) -> None:
    """П. 18 ПП 2463: продавец назван, ОГРНИП и адрес — на витрине."""
    content = client.get(url).content.decode()

    assert "ИП Иванов Иван Иванович" in content
    assert "323470000000001" in content
    assert "197198" in content


@pytest.mark.django_db
def test_empty_requisites_are_not_invented(client: Client) -> None:
    """Пустой реквизит не печатается — выдуманный хуже отсутствующего."""
    content = client.get("/contacts/").content.decode()

    assert "ОГРН/ОГРНИП:" not in content


def test_missing_requisites_are_reported_by_checks() -> None:
    """О незаполненных реквизитах молчать нельзя: политика без оператора.

    Витрина пустое поле не печатает, тесты механики зелёные — гарантию
    даёт `manage.py check`, куда смотрят перед выкладкой.
    """
    warnings = checks.seller_requisites_are_filled()

    assert [warning.id for warning in warnings] == [checks.MISSING_REQUISITES]


@pytest.mark.usefixtures("_requisites")
def test_filled_requisites_pass_the_check() -> None:
    assert checks.seller_requisites_are_filled() == []


@pytest.mark.django_db
@pytest.mark.usefixtures("products")
@pytest.mark.parametrize("url", PRICE_PAGES)
def test_prices_carry_the_offer_disclaimer(client: Client, url: str) -> None:
    """Цены витрины не связывают студию офертой (ст. 437 ГК РФ)."""
    content = client.get(url).content.decode()

    assert "не являются публичной офертой" in content


@pytest.mark.django_db
@pytest.mark.usefixtures("products")
@pytest.mark.parametrize("url", PAGES)
def test_responses_vary_on_the_consent_cookie(
    client: Client, url: str
) -> None:
    """Ответ зависит от cookie — кеш обязан это видеть (ADR-0006).

    Django ставит Vary только там, где потрогали сессию или CSRF,
    а баннер и счётчик решаются по cookie на любой странице.
    """
    response = client.get(url)

    assert "Cookie" in response.headers.get("Vary", "")
