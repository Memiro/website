import pytest
from dishka import AsyncContainer

from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.application.manage_products import AddVariant, AddVariantForm
from tests.common.factory.catalog import PRODUCT

pytestmark = pytest.mark.usefixtures("dictionary")


async def test_adding_fails_if_pricing_settings_are_not_found(
    request_container: AsyncContainer,
) -> None:
    """Missing pricing settings are rejected with PRICING_SETTINGS_NOT_FOUND."""
    interactor = await request_container.get(AddVariant)

    with pytest.raises(PricingSettingsNotFoundError):
        await interactor.execute(
            PRODUCT,
            AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0),
        )
