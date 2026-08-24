from decimal import Decimal
from http import HTTPStatus

import pytest
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import Client

from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    PricingSettings,
    Product,
    ProductAttribute,
)


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
        "description": "",
        "article": "",
        "order": "0",
        "gallery-TOTAL_FORMS": "0",
        "gallery-INITIAL_FORMS": "0",
        "attribute_values-TOTAL_FORMS": "0",
        "attribute_values-INITIAL_FORMS": "0",
        "variants-TOTAL_FORMS": "0",
        "variants-INITIAL_FORMS": "0",
        "_save": "",
    }
    payload.update(extra)
    return payload


@pytest.mark.django_db
def test_product_created_via_admin(
    admin_client: Client, category: Category
) -> None:
    """Владелец создаёт товар в админке."""
    response = admin_client.post(
        "/admin/catalog/product/add/",
        product_payload(category),
    )

    assert response.status_code == HTTPStatus.FOUND
    product = Product.objects.get(slug="luna")
    # Цену владелец не вводит: она приходит из вариантов (тикет 18)
    assert product.price is None
    assert not product.is_published


@pytest.mark.django_db
def test_own_category_attribute_accepted(
    admin_client: Client, category: Category
) -> None:
    """Атрибут своей категории сохраняется у товара."""
    attribute = Attribute.objects.create(
        category=category,
        name="Форма",
        slug="forma",
        kind=Attribute.Kind.CHOICE,
    )
    value = AttributeValue.objects.create(attribute=attribute, value="Круг")

    response = admin_client.post(
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
    admin_client: Client, category: Category
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

    response = admin_client.post(
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
    admin_client: Client, category: Category
) -> None:
    """Смена категории с чисткой атрибутов проходит одним сохранением.

    Строки, помеченные на удаление, формсет не валидирует.
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

    response = admin_client.post(
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


@pytest.fixture
def assigned_attribute(category: Category) -> Attribute:
    """Атрибут «Форма», уже назначенный товару через значение «Круг»."""
    attribute = Attribute.objects.create(
        category=category,
        name="Форма",
        slug="forma",
        kind=Attribute.Kind.CHOICE,
    )
    value = AttributeValue.objects.create(attribute=attribute, value="Круг")
    product = Product.objects.create(
        category=category, name="Зеркало", slug="z", price=PRICE
    )
    ProductAttribute.objects.create(
        product=product, attribute=attribute, value_option=value
    )
    return attribute


def attribute_payload(attribute: Attribute, **extra: object) -> dict:
    """Форма атрибута для POST в админку, инлайн значений нетронут."""
    payload: dict[str, object] = {
        "category": str(attribute.category_id),
        "name": attribute.name,
        "slug": attribute.slug,
        "kind": attribute.kind,
        "order": "0",
        "values-TOTAL_FORMS": "0",
        "values-INITIAL_FORMS": "0",
        "_save": "",
    }
    payload.update(extra)
    return payload


@pytest.mark.django_db
def test_assigned_attribute_category_change_blocked(
    admin_client: Client, assigned_attribute: Attribute
) -> None:
    """Категорию атрибута, назначенного товарам, не сменить:

    иначе товары молча остались бы с атрибутами чужой категории.
    """
    other = Category.objects.create(name="Перегородки", slug="peregorodki")

    response = admin_client.post(
        f"/admin/catalog/attribute/{assigned_attribute.pk}/change/",
        attribute_payload(assigned_attribute, category=str(other.pk)),
    )

    assert response.status_code == HTTPStatus.OK
    assigned_attribute.refresh_from_db()
    assert assigned_attribute.category_id != other.pk


@pytest.mark.django_db
def test_assigned_attribute_kind_change_blocked(
    admin_client: Client, assigned_attribute: Attribute
) -> None:
    """Тип атрибута, назначенного товарам, не сменить:

    значения у товаров перестали бы соответствовать типу.
    """
    response = admin_client.post(
        f"/admin/catalog/attribute/{assigned_attribute.pk}/change/",
        attribute_payload(
            assigned_attribute, kind=Attribute.Kind.NUMBER.value
        ),
    )

    assert response.status_code == HTTPStatus.OK
    assigned_attribute.refresh_from_db()
    assert assigned_attribute.kind == Attribute.Kind.CHOICE


@pytest.mark.django_db
def test_used_attribute_value_is_protected(
    assigned_attribute: Attribute,
) -> None:
    """Значение справочника, назначенное товарам, не удалить —

    чистка справочника не должна молча стирать характеристики.
    """
    value = assigned_attribute.values.get()

    with pytest.raises(ProtectedError):
        value.delete()


@pytest.mark.django_db
def test_assigned_attribute_is_protected_until_unassigned(
    assigned_attribute: Attribute,
) -> None:
    """Атрибут, назначенный товарам, не удалить; снятый с товаров —

    удаляется вместе со своим справочником значений.
    """
    with pytest.raises(ProtectedError):
        assigned_attribute.delete()

    ProductAttribute.objects.all().delete()
    assigned_attribute.delete()

    assert not AttributeValue.objects.exists()


# --- Тарифы справочника (ADR-0007) ---

LED_RATE = Decimal("2500.00")
BUTTON_RATE = Decimal("1500.00")
MIN_ORDER_TOTAL = 9000
MIN_AREA = Decimal("0.400")
# «Подсветка» и «Кнопка», сохранённые одним submit
EXPECTED_ATTRIBUTES = 2


@pytest.fixture
def lighting(category: Category) -> Attribute:
    """Атрибут «Подсветка» с тарифицированным значением."""
    attribute = Attribute.objects.create(
        category=category,
        name="Подсветка",
        slug="podsvetka",
        kind=Attribute.Kind.CHOICE,
    )
    AttributeValue.objects.create(
        attribute=attribute,
        value="Контурная",
        unit=AttributeValue.Unit.LINEAR_METER,
        rate=LED_RATE,
    )
    return attribute


@pytest.fixture
def button(category: Category, lighting: Attribute) -> Attribute:
    """Атрибут «Кнопка»: без подсветки его не бывает."""
    attribute = Attribute.objects.create(
        category=category,
        name="Кнопка",
        slug="knopka",
        kind=Attribute.Kind.CHOICE,
    )
    attribute.parents.add(lighting)
    AttributeValue.objects.create(
        attribute=attribute,
        value="Сенсорная",
        unit=AttributeValue.Unit.PIECE,
        rate=BUTTON_RATE,
    )
    return attribute


@pytest.mark.django_db
def test_tariff_entered_in_admin(
    admin_client: Client, category: Category
) -> None:
    """Владелец заводит тариф строкой справочника, и он читается обратно.

    «Контурная подсветка — 2 500 ₽ за погонный метр»: ставка и единица
    расхода вводятся там же, где значение, — отдельной модели нет.
    """
    attribute = Attribute.objects.create(
        category=category,
        name="Подсветка",
        slug="podsvetka",
        kind=Attribute.Kind.CHOICE,
    )

    response = admin_client.post(
        f"/admin/catalog/attribute/{attribute.pk}/change/",
        attribute_payload(
            attribute,
            **{
                "values-TOTAL_FORMS": "1",
                "values-0-value": "Контурная",
                "values-0-unit": AttributeValue.Unit.LINEAR_METER.value,
                "values-0-rate": str(LED_RATE),
                "values-0-order": "0",
            },
        ),
    )

    assert response.status_code == HTTPStatus.FOUND
    value = AttributeValue.objects.get(attribute=attribute)
    assert value.unit == AttributeValue.Unit.LINEAR_METER
    assert value.rate == LED_RATE


@pytest.mark.django_db
def test_value_without_tariff_is_free(category: Category) -> None:
    """Незаполненный тариф — «бесплатно», а не ошибка.

    Иначе 425 значений перенесённых товаров не пережили бы миграцию.
    """
    attribute = Attribute.objects.create(
        category=category,
        name="Цвет рамы",
        slug="cvet-ramy",
        kind=Attribute.Kind.CHOICE,
    )
    value = AttributeValue(attribute=attribute, value="Чёрный")
    value.full_clean()
    value.save()

    assert not value.unit
    assert value.rate is None


@pytest.mark.django_db
def test_tariff_needs_unit_and_rate_together(category: Category) -> None:
    """Ставка без единицы (и наоборот) — половина тарифа, её не сохранить."""
    attribute = Attribute.objects.create(
        category=category,
        name="Форма",
        slug="forma",
        kind=Attribute.Kind.CHOICE,
    )

    with pytest.raises(ValidationError):
        AttributeValue(
            attribute=attribute, value="Круглое", rate=Decimal("1.5")
        ).full_clean()
    with pytest.raises(ValidationError):
        AttributeValue(
            attribute=attribute,
            value="Круглое",
            unit=AttributeValue.Unit.FACTOR,
        ).full_clean()


@pytest.mark.django_db
def test_orphan_child_value_is_rejected(
    admin_client: Client, category: Category, button: Attribute
) -> None:
    """Кнопка без подсветки не сохраняется, и админка объясняет почему."""
    value = button.values.get()

    response = admin_client.post(
        "/admin/catalog/product/add/",
        product_payload(
            category,
            **{
                "attribute_values-TOTAL_FORMS": "1",
                "attribute_values-0-attribute": str(button.pk),
                "attribute_values-0-value_option": str(value.pk),
            },
        ),
    )

    assert response.status_code == HTTPStatus.OK
    assert not Product.objects.exists()
    assert "Подсветка" in response.content.decode()


@pytest.mark.django_db
def test_parent_answered_no_is_not_a_parent(
    admin_client: Client, category: Category, button: Attribute
) -> None:
    """«Подогрев: нет» — отсутствие признака, кнопке он не родитель."""
    heating = Attribute.objects.create(
        category=category,
        name="Подогрев",
        slug="podogrev",
        kind=Attribute.Kind.BOOLEAN,
    )
    button.parents.set([heating])

    response = admin_client.post(
        "/admin/catalog/product/add/",
        product_payload(
            category,
            **{
                "attribute_values-TOTAL_FORMS": "2",
                "attribute_values-0-attribute": str(heating.pk),
                "attribute_values-0-value_bool": "false",
                "attribute_values-1-attribute": str(button.pk),
                "attribute_values-1-value_option": str(button.values.get().pk),
            },
        ),
    )

    assert response.status_code == HTTPStatus.OK
    assert not Product.objects.exists()
    assert "Подогрев" in response.content.decode()


@pytest.mark.django_db
def test_child_saved_together_with_parent(
    admin_client: Client,
    category: Category,
    lighting: Attribute,
    button: Attribute,
) -> None:
    """Родителя и ребёнка владелец заводит одним сохранением."""
    response = admin_client.post(
        "/admin/catalog/product/add/",
        product_payload(
            category,
            **{
                "attribute_values-TOTAL_FORMS": "2",
                "attribute_values-0-attribute": str(lighting.pk),
                "attribute_values-0-value_option": str(
                    lighting.values.get().pk
                ),
                "attribute_values-1-attribute": str(button.pk),
                "attribute_values-1-value_option": str(button.values.get().pk),
            },
        ),
    )

    assert response.status_code == HTTPStatus.FOUND
    saved = Product.objects.get(slug="luna")
    assert saved.attribute_values.count() == EXPECTED_ATTRIBUTES


@pytest.mark.django_db
def test_foreign_category_parent_rejected(
    admin_client: Client, lighting: Attribute, button: Attribute
) -> None:
    """Родитель из чужой категории у атрибута не заводится:

    товару такого родителя не назначить, и кнопка осталась бы
    несохраняемой навсегда.
    """
    other = Category.objects.create(name="Перегородки", slug="peregorodki")
    foreign = Attribute.objects.create(
        category=other,
        name="Профиль",
        slug="profil",
        kind=Attribute.Kind.CHOICE,
    )

    response = admin_client.post(
        f"/admin/catalog/attribute/{button.pk}/change/",
        attribute_payload(button, parents=[str(foreign.pk)]),
    )

    assert response.status_code == HTTPStatus.OK
    assert "другой категории" in response.content.decode()
    assert list(button.parents.all()) == [lighting]


@pytest.mark.django_db
def test_parent_cycle_rejected(
    admin_client: Client, lighting: Attribute, button: Attribute
) -> None:
    """Кольцо зависимостей не завести: в нём не сохранить ни одного из.

    Кнопка уже зависит от подсветки; подсветка, зависящая от кнопки,
    сделала бы оба атрибута неназначаемыми.
    """
    response = admin_client.post(
        f"/admin/catalog/attribute/{lighting.pk}/change/",
        attribute_payload(lighting, parents=[str(button.pk)]),
    )

    assert response.status_code == HTTPStatus.OK
    assert "уже опирается на этот атрибут" in response.content.decode()
    assert not lighting.parents.exists()


@pytest.mark.django_db
def test_customer_editable_flag_stored(
    admin_client: Client, lighting: Attribute
) -> None:
    """Признак «меняет покупатель» владелец ставит в админке."""
    assert not lighting.is_customer_editable

    response = admin_client.post(
        f"/admin/catalog/attribute/{lighting.pk}/change/",
        attribute_payload(lighting, is_customer_editable="on"),
    )

    assert response.status_code == HTTPStatus.FOUND
    lighting.refresh_from_db()
    assert lighting.is_customer_editable


@pytest.mark.django_db
def test_pricing_limits_are_data(admin_client: Client) -> None:
    """Минимальная площадь и минимальная сумма заводятся в админке."""
    response = admin_client.post(
        "/admin/catalog/pricingsettings/add/",
        {
            "min_area_m2": str(MIN_AREA),
            "min_order_total": str(MIN_ORDER_TOTAL),
            "_save": "",
        },
    )

    assert response.status_code == HTTPStatus.FOUND
    saved = PricingSettings.objects.get()
    assert saved.min_area_m2 == MIN_AREA
    assert saved.min_order_total == MIN_ORDER_TOTAL


@pytest.mark.django_db
def test_pricing_limits_stay_single_row(admin_client: Client) -> None:
    """Параметры расчёта одни на сайт — второй строки не завести."""
    PricingSettings.objects.create(
        min_area_m2=MIN_AREA, min_order_total=MIN_ORDER_TOTAL
    )

    response = admin_client.get("/admin/catalog/pricingsettings/add/")

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert PricingSettings.objects.count() == 1
