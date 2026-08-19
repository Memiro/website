from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client

from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    Product,
    ProductAttribute,
)


@pytest.fixture
def admin(client: Client) -> Client:
    """Клиент, вошедший в админку суперпользователем."""
    get_user_model().objects.create_superuser(
        username="owner",
        email="owner@example.com",
        password="owner-password",
    )
    client.login(username="owner", password="owner-password")
    return client


@pytest.fixture
def category() -> Category:
    return Category.objects.create(name="Зеркала", slug="zerkala")


PRICE = 12000


def product_payload(category: Category, **extra: object) -> dict[str, object]:
    """Валидная форма товара для POST в админку, инлайны пустые."""
    payload: dict[str, object] = {
        "category": category.pk,
        "name": "Зеркало «Луна»",
        "slug": "luna",
        "price": str(PRICE),
        "description": "",
        "article": "",
        "order": "0",
        "gallery-TOTAL_FORMS": "0",
        "gallery-INITIAL_FORMS": "0",
        "attribute_values-TOTAL_FORMS": "0",
        "attribute_values-INITIAL_FORMS": "0",
        "_save": "",
    }
    payload.update(extra)
    return payload


@pytest.mark.django_db
def test_product_created_via_admin(admin: Client, category: Category) -> None:
    """Владелец создаёт товар в админке."""
    response = admin.post(
        "/admin/catalog/product/add/",
        product_payload(category),
    )

    assert response.status_code == HTTPStatus.FOUND
    product = Product.objects.get(slug="luna")
    assert product.price == PRICE
    assert not product.is_published


@pytest.mark.django_db
def test_product_price_is_required(admin: Client, category: Category) -> None:
    """Без цены товар не сохраняется — режима «цена по запросу» нет."""
    response = admin.post(
        "/admin/catalog/product/add/",
        product_payload(category, price=""),
    )

    assert response.status_code == HTTPStatus.OK
    assert not Product.objects.exists()


@pytest.mark.django_db
def test_product_price_must_be_positive(
    admin: Client, category: Category
) -> None:
    """Нулевая цена отклоняется валидацией."""
    response = admin.post(
        "/admin/catalog/product/add/",
        product_payload(category, price="0"),
    )

    assert response.status_code == HTTPStatus.OK
    assert not Product.objects.exists()


@pytest.mark.django_db
def test_own_category_attribute_accepted(
    admin: Client, category: Category
) -> None:
    """Атрибут своей категории сохраняется у товара."""
    attribute = Attribute.objects.create(
        category=category,
        name="Форма",
        slug="forma",
        kind=Attribute.Kind.CHOICE,
    )
    value = AttributeValue.objects.create(attribute=attribute, value="Круг")

    response = admin.post(
        "/admin/catalog/product/add/",
        product_payload(
            category,
            **{
                "attribute_values-TOTAL_FORMS": "1",
                "attribute_values-0-attribute": str(attribute.pk),
                "attribute_values-0-value_option": str(value.pk),
            },
        ),
    )

    assert response.status_code == HTTPStatus.FOUND
    saved = Product.objects.get(slug="luna").attribute_values.get()
    assert saved.value_option == value


@pytest.mark.django_db
def test_foreign_category_attribute_rejected(
    admin: Client, category: Category
) -> None:
    """Атрибут чужой категории товару не назначить."""
    other = Category.objects.create(name="Перегородки", slug="peregorodki")
    foreign = Attribute.objects.create(
        category=other,
        name="Профиль",
        slug="profil",
        kind=Attribute.Kind.CHOICE,
    )
    value = AttributeValue.objects.create(attribute=foreign, value="Чёрный")

    response = admin.post(
        "/admin/catalog/product/add/",
        product_payload(
            category,
            **{
                "attribute_values-TOTAL_FORMS": "1",
                "attribute_values-0-attribute": str(foreign.pk),
                "attribute_values-0-value_option": str(value.pk),
            },
        ),
    )

    assert response.status_code == HTTPStatus.OK
    assert not Product.objects.exists()


@pytest.mark.django_db
def test_attribute_value_must_match_kind(category: Category) -> None:
    """Значение атрибута обязано соответствовать его типу."""
    product = Product.objects.create(
        category=category, name="Зеркало", slug="z", price=10000
    )
    boolean = Attribute.objects.create(
        category=category,
        name="Подсветка",
        slug="podsvetka",
        kind=Attribute.Kind.BOOLEAN,
    )

    assignment = ProductAttribute(
        product=product, attribute=boolean, value_number=5
    )
    with pytest.raises(ValidationError):
        assignment.full_clean()

    assignment = ProductAttribute(
        product=product, attribute=boolean, value_bool=True
    )
    assignment.full_clean()


@pytest.mark.django_db
def test_category_visible_only_with_published_products(
    category: Category,
) -> None:
    """Категория видима, только когда в ней есть опубликованные товары."""
    empty = Category.objects.create(name="Пустая", slug="pustaia")
    drafts_only = Category.objects.create(name="Черновики", slug="chernoviki")
    Product.objects.create(
        category=drafts_only, name="Черновик", slug="d", price=1000
    )
    Product.objects.create(
        category=category,
        name="Зеркало",
        slug="z",
        price=10000,
        is_published=True,
    )

    visible = Category.objects.visible()

    assert category in visible
    assert empty not in visible
    assert drafts_only not in visible


@pytest.mark.django_db
def test_category_change_with_attribute_removal_is_one_step(
    admin: Client, category: Category
) -> None:
    """Смена категории с удалением старых атрибутов проходит одним

    сохранением: строки, помеченные на удаление, не валидируются.
    """
    other = Category.objects.create(name="Перегородки", slug="peregorodki")
    attribute = Attribute.objects.create(
        category=category,
        name="Форма",
        slug="forma",
        kind=Attribute.Kind.CHOICE,
    )
    value = AttributeValue.objects.create(attribute=attribute, value="Круг")
    product = Product.objects.create(
        category=category, name="Зеркало «Луна»", slug="luna", price=PRICE
    )
    assignment = ProductAttribute.objects.create(
        product=product, attribute=attribute, value_option=value
    )

    response = admin.post(
        f"/admin/catalog/product/{product.pk}/change/",
        product_payload(
            other,
            **{
                "attribute_values-TOTAL_FORMS": "1",
                "attribute_values-INITIAL_FORMS": "1",
                "attribute_values-0-id": str(assignment.pk),
                "attribute_values-0-attribute": str(attribute.pk),
                "attribute_values-0-value_option": str(value.pk),
                "attribute_values-0-DELETE": "on",
            },
        ),
    )

    assert response.status_code == HTTPStatus.FOUND
    product.refresh_from_db()
    assert product.category == other
    assert not product.attribute_values.exists()
