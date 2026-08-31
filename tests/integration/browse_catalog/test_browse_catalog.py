from fastapi import status

from memiro.application.browse_catalog import CategoryModel, ProductModel
from memiro.application.browse_catalog.models import ProductAttribute, ProductAttributeValue
from tests.common.factory.catalog import (
    ALUMINIUM,
    BACKLIGHT,
    BLADE,
    CONTOUR,
    FRAME,
    GRAPHITE,
    MOUNT,
    NO_BACKLIGHT,
    NO_FRAME,
    NO_MOUNT,
    PRODUCT,
    RECTANGULAR,
    ROUND,
    SHAPE,
    SILVER,
    WITH_MOUNT,
)
from tests.integration.api_client import ApiClient


async def test_catalog_lists_categories_with_published_products(
    api_client: ApiClient,
    catalog: None,  # noqa: ARG001
) -> None:
    """Published categories are listed in the owner order."""
    assert (await api_client.list_categories()).assert_status(status.HTTP_200_OK).ensure_content() == [
        CategoryModel(name="Mirrors", slug="mirrors"),
    ]


async def test_a_product_card_exposes_the_identifier_the_calculator_needs(
    api_client: ApiClient,
    catalog: None,  # noqa: ARG001
) -> None:
    """A public product card names its UUID for the next calculate request."""
    assert (await api_client.read_product("zerkalo-v-rame")).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == ProductModel(
        id=PRODUCT,
        name="Зеркало в раме",
        slug="zerkalo-v-rame",
        price_from=None,
        image_keys=[],
        description="A made-to-order mirror.",
        attributes=[
            ProductAttribute(
                id=BLADE,
                name="Тип полотна",
                values=[
                    ProductAttributeValue(id=SILVER, name="Серебро", quantity=None),  # noqa: RUF001
                    ProductAttributeValue(id=GRAPHITE, name="Графит", quantity=None),
                ],
            ),
            ProductAttribute(
                id=SHAPE,
                name="Форма",
                values=[
                    ProductAttributeValue(id=RECTANGULAR, name="Прямоугольное", quantity=None),
                    ProductAttributeValue(id=ROUND, name="Круглое", quantity=None),
                ],
            ),
            ProductAttribute(
                id=FRAME,
                name="Рама",
                values=[
                    ProductAttributeValue(id=ALUMINIUM, name="Алюминий", quantity=None),
                    ProductAttributeValue(id=NO_FRAME, name="Без рамы", quantity=None),
                ],
            ),
            ProductAttribute(
                id=BACKLIGHT,
                name="Подсветка",
                values=[
                    ProductAttributeValue(id=CONTOUR, name="Контурная", quantity=None),
                    ProductAttributeValue(id=NO_BACKLIGHT, name="Без подсветки", quantity=None),
                ],
            ),
            ProductAttribute(
                id=MOUNT,
                name="Крепление",
                values=[
                    ProductAttributeValue(id=WITH_MOUNT, name="С креплением", quantity=None),  # noqa: RUF001
                    ProductAttributeValue(id=NO_MOUNT, name="Без крепления", quantity=None),
                ],
            ),
        ],
        variants=[],
    )
