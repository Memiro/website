import pytest
from dishka import AsyncContainer

from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.application.manage_products import ChangeVariant, ChangeVariantForm
from tests.common.factory.catalog import PRODUCT
from tests.integration.manage_products.setup import prime_variant

pytestmark = pytest.mark.usefixtures("dictionary")


async def test_changing_fails_if_pricing_settings_are_not_found(
    request_container: AsyncContainer,
) -> None:
    """Missing pricing settings are rejected with PRICING_SETTINGS_NOT_FOUND."""
    variant_id = await prime_variant(request_container)
    interactor = await request_container.get(ChangeVariant)

    with pytest.raises(PricingSettingsNotFoundError):
        await interactor.execute(
            PRODUCT,
            variant_id,
            ChangeVariantForm(width_mm=1200, height_mm=800, overrides=[], sort_order=0),
        )
