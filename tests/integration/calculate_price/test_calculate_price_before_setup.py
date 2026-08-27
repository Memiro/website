import pytest

from memiro.application.calculate_price import CalculatePriceForm
from tests.common.factory.catalog import PRODUCT
from tests.integration.api_client import ApiClient

# The dictionary is in place, the pricing settings are not: the site has a
# catalogue but nothing to calculate its bounds from.
pytestmark = pytest.mark.usefixtures("dictionary")


async def test_pricing_fails_if_the_pricing_settings_were_never_created(api_client: ApiClient) -> None:
    """Without the single settings row the calculation is refused with PRICING_SETTINGS_NOT_FOUND."""
    form = CalculatePriceForm(product_id=PRODUCT, width_mm=800, height_mm=600, selections=[])

    response = await api_client.calculate(form)

    response.assert_error(404, "PRICING_SETTINGS_NOT_FOUND")
