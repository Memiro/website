from fastapi import status

from tests.common.factory.catalog import PRODUCT
from tests.integration.api_client import ApiClient


async def test_catalog_lists_categories_with_published_products(
    api_client: ApiClient,
    catalog: None,  # noqa: ARG001
) -> None:
    """Published categories are listed in the owner order."""
    response = await api_client.list_categories()

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [{"name": "Mirrors", "slug": "mirrors"}]


async def test_a_product_card_exposes_the_identifier_the_calculator_needs(
    api_client: ApiClient,
    catalog: None,  # noqa: ARG001
) -> None:
    """A public product card names its UUID for the next calculate request."""
    response = await api_client.read_product("zerkalo-v-rame")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == str(PRODUCT)
