"""Тикет 08: отзывы, FAQ и акции — из админки на витрину."""

from http import HTTPStatus
from importlib import import_module

import pytest
from django.apps import apps
from django.test import Client

from memiro.catalog.models import Category, Product
from memiro.content.models import FaqEntry, Promo, Review

# Имя модуля миграции начинается с цифры — обычным import не взять
sale_migration = import_module(
    "memiro.content.migrations.0003_promo_for_existing_sale"
)

pytestmark = pytest.mark.django_db


# ---------- Отзывы ----------


def test_home_shows_published_review(client: Client) -> None:
    Review.objects.create(
        author="Мария",
        text="Зеркало сделали за три дня, повесили аккуратно.",
        source="Avito",
        is_published=True,
    )

    content = client.get("/").content.decode()

    assert "Отзывы" in content
    assert "Мария" in content
    assert "повесили аккуратно" in content


def test_home_hides_unpublished_review(client: Client) -> None:
    Review.objects.create(
        author="Скрытый автор",
        text="Черновой отзыв",
        source="Avito",
    )

    content = client.get("/").content.decode()

    assert "Скрытый автор" not in content
    assert "Черновой отзыв" not in content


def test_home_hides_reviews_section_without_reviews(client: Client) -> None:
    """Проверяем по разметке секции: слово «отзывы» переживёт ссылку в меню."""
    content = client.get("/").content.decode()

    assert "reviews-grid" not in content


def test_home_shows_every_published_review(client: Client) -> None:
    """Потолка на главной нет: опубликовал — увидел."""
    published_count = 5
    for number in range(published_count):
        Review.objects.create(
            author=f"Автор {number}",
            text="Спасибо",
            source="Avito",
            is_published=True,
            order=number,
        )

    content = client.get("/").content.decode()

    assert content.count('class="review"') == published_count


def test_reviews_ordered_manually(client: Client) -> None:
    Review.objects.create(
        author="Вторая", text="Б", source="Avito", is_published=True, order=2
    )
    Review.objects.create(
        author="Первая", text="А", source="Avito", is_published=True, order=1
    )

    content = client.get("/").content.decode()

    assert content.index("Первая") < content.index("Вторая")


def test_review_shows_source(client: Client) -> None:
    """Отзыв заносится вручную — источник виден посетителю."""
    Review.objects.create(
        author="Мария", text="Отлично", source="Avito", is_published=True
    )

    content = client.get("/").content.decode()

    assert "Avito" in content


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


def test_home_shows_published_promo(client: Client) -> None:
    Promo.objects.create(
        title="Весенние скидки",
        text="Подробности уточняйте у менеджера.",
        is_published=True,
    )

    content = client.get("/").content.decode()

    assert "Весенние скидки" in content
    assert "Подробности уточняйте у менеджера." in content


def test_home_hides_unpublished_promo(client: Client) -> None:
    Promo.objects.create(title="Скрытая акция", is_published=False)

    content = client.get("/").content.decode()

    assert "Скрытая акция" not in content


def test_promo_block_carries_promo_products(
    client: Client, promo_product: Product
) -> None:
    Promo.objects.create(title="Весенние скидки", is_published=True)

    content = client.get("/").content.decode()

    assert content.index("Весенние скидки") < content.index("Dew Glow")


def test_promo_products_hidden_without_published_promo(
    client: Client, promo_product: Product
) -> None:
    """Блок акции живёт из админки: нет акции — нет и её ленты товаров."""
    content = client.get("/").content.decode()

    assert "Dew Glow" not in content


def test_first_promo_by_order_wins(client: Client) -> None:
    Promo.objects.create(title="Вторая акция", is_published=True, order=2)
    Promo.objects.create(title="Первая акция", is_published=True, order=1)

    content = client.get("/").content.decode()

    assert "Первая акция" in content
    assert "Вторая акция" not in content


def test_migration_keeps_existing_sale_block(
    client: Client, promo_product: Product
) -> None:
    """Витрина с уже отмеченными товарами не теряет блок при переезде."""
    sale_migration.create_promo_for_flagged_products(apps, None)

    content = client.get("/").content.decode()

    assert sale_migration.LEGACY_TITLE in content
    assert "Dew Glow" in content


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


def test_review_created_through_admin_appears_on_site(
    admin_client: Client, client: Client
) -> None:
    """Путь владельца целиком: форма админки → отзыв на главной."""
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
    assert "Ольга" in client.get("/").content.decode()


def test_promo_hidden_from_site_after_unpublishing_in_admin(
    admin_client: Client, client: Client, promo_product: Product
) -> None:
    """Снятая с публикации акция уносит с главной и свою ленту товаров."""
    promo = Promo.objects.create(title="Весенние скидки", is_published=True)

    admin_client.post(
        f"/admin/content/promo/{promo.pk}/change/",
        {"title": promo.title, "text": "", "order": "0"},
    )
    content = client.get("/").content.decode()

    assert "Весенние скидки" not in content
    assert "Dew Glow" not in content
