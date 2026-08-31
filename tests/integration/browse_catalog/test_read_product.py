from decimal import Decimal

import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.browse_catalog import ProductModel
from memiro.application.browse_catalog.models import (
    ProductAttribute,
    ProductAttributeValue,
    ProductVariant,
    VariantOverride,
)
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
from tests.integration.prime import (
    prime_hidden_calculated_price,
    prime_product_images,
    prime_product_publication,
)

pytestmark = pytest.mark.usefixtures("catalog")

IMAGE_KEYS = ["mirror-side.jpg", "mirror-front.jpg"]
# The two variants of the ``variants`` fixture, in the owner's order.
OWNER_ORDERED_VARIANTS = [
    ProductVariant(
        width_mm=800,
        height_mm=600,
        price=Decimal(2700),
        overrides=[VariantOverride(attribute_id=FRAME, value_id=NO_FRAME, quantity=None)],
    ),
    ProductVariant(width_mm=800, height_mm=600, price=Decimal(8900), overrides=[]),
]


def _expected_card(
    *,
    price_from: Decimal | None = None,
    image_keys: list[str] | None = None,
    variants: list[ProductVariant] | None = None,
) -> ProductModel:
    """Build the whole expected card around the part a scenario changes."""
    return ProductModel(
        id=PRODUCT,
        name="Зеркало в раме",
        slug="zerkalo-v-rame",
        price_from=price_from,
        image_keys=image_keys or [],
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
        variants=variants or [],
    )


async def test_a_product_card_exposes_the_identifier_the_calculator_needs(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A public card names its UUID, its description, its photos and the owner-ordered attribute values."""
    await prime_product_images(engine)

    assert (await api_client.read_product("zerkalo-v-rame")).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == _expected_card(image_keys=IMAGE_KEYS)


async def test_a_card_lists_the_variants_in_the_order_the_owner_gave_them(
    api_client: ApiClient,
    variants: None,  # noqa: ARG001
) -> None:
    """The cheaper variant the owner put first arrives first, and the card's price starts at it."""
    assert (await api_client.read_product("zerkalo-v-rame")).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == _expected_card(price_from=Decimal(2700), variants=OWNER_ORDERED_VARIANTS)


async def test_a_hidden_calculated_price_keeps_the_precalculated_variants_visible(
    api_client: ApiClient,
    engine: AsyncEngine,
    variants: None,  # noqa: ARG001
) -> None:
    """A product whose calculated price is hidden from customers still shows its stored price_from."""
    await prime_hidden_calculated_price(engine)

    assert (await api_client.read_product("zerkalo-v-rame")).assert_status(
        status.HTTP_200_OK
    ).ensure_content() == _expected_card(price_from=Decimal(2700), variants=OWNER_ORDERED_VARIANTS)


async def test_reading_fails_if_no_product_carries_the_slug(api_client: ApiClient) -> None:
    """A slug nobody issued is rejected with PRODUCT_NOT_FOUND."""
    (await api_client.read_product("no-such-product")).assert_error(status.HTTP_404_NOT_FOUND, "PRODUCT_NOT_FOUND")


async def test_reading_fails_if_the_product_is_not_published(api_client: ApiClient, engine: AsyncEngine) -> None:
    """An unpublished product is rejected with PRODUCT_NOT_FOUND — the storefront learns nothing of it."""
    await prime_product_publication(engine, is_published=False)

    (await api_client.read_product("zerkalo-v-rame")).assert_error(status.HTTP_404_NOT_FOUND, "PRODUCT_NOT_FOUND")


async def test_the_card_says_nothing_about_how_the_price_is_made(
    api_client: ApiClient,
    variants: None,  # noqa: ARG001
) -> None:
    """The public card carries no tariffs, no factors and no lines of blade and edge."""
    body = (await api_client.read_product("zerkalo-v-rame")).assert_status(status.HTTP_200_OK).text

    assert "4500" not in body
    assert "2200" not in body
    assert "rate" not in body
    assert "breakdown" not in body
    assert "factor" not in body
