"""Отзывы, FAQ и акции: что из админки выходит на витрину, а что нет.

FAQ выходит (тикет 08). Акции (тикет 05) и отзывы (тикет 06 набора
`owner-revision`) — нет: разделы админки живы, и тесты стерегут именно
это — заведённое сохраняется и на сайте не всплывает.
"""

from http import HTTPStatus
from importlib import import_module

import pytest
from django.apps import apps
from django.contrib.admin.sites import AdminSite
from django.forms.models import fields_for_model
from django.test import Client, RequestFactory

from memiro.catalog.models import Category, Product
from memiro.content.admin import ReviewAdmin
from memiro.content.models import FaqEntry, Promo, Review

# Имя модуля миграции начинается с цифры — обычным import не взять
sale_migration = import_module(
    "memiro.content.migrations.0003_promo_for_existing_sale"
)

pytestmark = pytest.mark.django_db


# ---------- Отзывы ----------


def test_home_hides_published_review(client: Client) -> None:
    """Тикет 06: отзыв публикуется в админке и на витрину не выходит."""
    Review.objects.create(
        author="Мария",
        text="Зеркало сделали за три дня, повесили аккуратно.",
        source="Avito",
        is_published=True,
    )

    content = client.get("/").content.decode()

    assert "Мария" not in content
    assert "повесили аккуратно" not in content
    # Разметка секции, а не слово «отзывы»: оно переживёт ссылку в меню
    assert "reviews-grid" not in content


# ---------- FAQ ----------


def test_home_shows_published_faq(client: Client) -> None:
    FaqEntry.objects.create(
        question="Сколько делается зеркало?",
        answer="От одного рабочего дня.",
        is_published=True,
    )

    content = client.get("/").content.decode()

    assert "Сколько делается зеркало?" in content
    assert "От одного рабочего дня." in content


def test_home_hides_unpublished_faq(client: Client) -> None:
    FaqEntry.objects.create(
        question="Скрытый вопрос",
        answer="Скрытый ответ",
    )

    content = client.get("/").content.decode()

    assert "Скрытый вопрос" not in content


def test_home_hides_faq_section_without_entries(client: Client) -> None:
    content = client.get("/").content.decode()

    assert "faq-item" not in content


def test_faq_ordered_manually(client: Client) -> None:
    FaqEntry.objects.create(
        question="Второй вопрос", answer="Б", is_published=True, order=2
    )
    FaqEntry.objects.create(
        question="Первый вопрос", answer="А", is_published=True, order=1
    )

    content = client.get("/").content.decode()

    assert content.index("Первый вопрос") < content.index("Второй вопрос")


# ---------- Акции ----------


@pytest.fixture
def promo_product(db: None) -> Product:
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    return Product.objects.create(
        category=category,
        name="Dew Glow",
        slug="dew-glow",
        price=7998,
        is_published=True,
        is_promo=True,
    )


def test_home_hides_published_promo(
    client: Client, promo_product: Product
) -> None:
    """Тикет 05: акция публикуется в админке и на витрину не выходит."""
    Promo.objects.create(
        title="Весенние скидки",
        text="Подробности уточняйте у менеджера.",
        is_published=True,
    )

    content = client.get("/").content.decode()

    assert "Весенние скидки" not in content
    assert "Подробности уточняйте у менеджера." not in content
    assert "Dew Glow" not in content


def test_promo_flag_gives_no_badge_on_home(
    client: Client, promo_product: Product
) -> None:
    """Флаг «акция» у товара витрину не метит — даже в ленте популярного."""
    Product.objects.filter(pk=promo_product.pk).update(is_popular=True)

    content = client.get("/").content.decode()

    assert "Dew Glow" in content
    assert "Акция" not in content


def test_migration_keeps_flagged_showcase_promo(
    client: Client, promo_product: Product
) -> None:
    """Данные переезда живы: запись заводится, хоть её и не видно."""
    sale_migration.create_promo_for_flagged_products(apps, None)

    assert Promo.objects.filter(title=sale_migration.LEGACY_TITLE).exists()
    assert sale_migration.LEGACY_TITLE not in client.get("/").content.decode()


def test_migration_skips_showcase_without_flagged_products(db: None) -> None:
    sale_migration.create_promo_for_flagged_products(apps, None)

    assert not Promo.objects.exists()


# ---------- Админка ----------


@pytest.mark.parametrize(
    "url",
    [
        "/admin/content/review/",
        "/admin/content/faqentry/",
        "/admin/content/promo/",
    ],
)
def test_admin_sections_registered(admin_client: Client, url: str) -> None:
    assert admin_client.get(url).status_code == HTTPStatus.OK


def test_review_form_covers_every_editable_field(rf: RequestFactory) -> None:
    """Явный `fieldsets` молча теряет новое поле — а симптом у владельца
    тот же, ради которого подсказку и добавляли: заведённое ушло в никуда.
    """
    form = ReviewAdmin(Review, AdminSite()).get_form(rf.get("/"))()

    assert set(form.fields) == set(fields_for_model(Review))


def test_review_created_through_admin_stays_off_the_site(
    admin_client: Client, client: Client
) -> None:
    """Путь владельца целиком: форма админки принимает, витрина молчит."""
    response = admin_client.post(
        "/admin/content/review/add/",
        {
            "author": "Ольга",
            "text": "Повесили ровно, всё понравилось.",
            "source": "Avito",
            "source_url": "",
            "rating": "5",
            "is_published": "on",
            "order": "0",
        },
    )

    assert response.status_code == HTTPStatus.FOUND
    assert Review.objects.filter(author="Ольга").exists()
    assert "Ольга" not in client.get("/").content.decode()


def test_promo_edited_in_admin_stays_off_the_site(
    admin_client: Client, client: Client, promo_product: Product
) -> None:
    """Акция остаётся живой записью админки — и после правки не всплывает."""
    promo = Promo.objects.create(title="Весенние скидки", is_published=True)

    response = admin_client.post(
        f"/admin/content/promo/{promo.pk}/change/",
        {
            "title": promo.title,
            "text": "",
            "is_published": "on",
            "order": "0",
        },
    )
    content = client.get("/").content.decode()

    assert response.status_code == HTTPStatus.FOUND
    assert Promo.objects.get(pk=promo.pk).is_published
    assert "Весенние скидки" not in content
    assert "Dew Glow" not in content
