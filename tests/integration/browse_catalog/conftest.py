import pytest
from dishka import AsyncContainer
from fastapi import FastAPI

from memiro.application.manage_products import AddVariant, AddVariantForm
from memiro.application.manage_products.shared import VariantOverrideForm
from tests.common.factory.catalog import FRAME, NO_FRAME, PRODUCT

CHEAP_VARIANT = AddVariantForm(
    width_mm=800,
    height_mm=600,
    overrides=[VariantOverrideForm(attribute_id=FRAME, value_id=NO_FRAME)],
    sort_order=1,
)
WORKBOOK_VARIANT = AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=2)


@pytest.fixture
async def variants(app: FastAPI, catalog: None) -> None:  # noqa: ARG001
    """Give the canonical product two precalculated variants through the owner's own use case."""
    container: AsyncContainer = app.state.dishka_container
    for form in (WORKBOOK_VARIANT, CHEAP_VARIANT):
        async with container() as request:
            interactor = await request.get(AddVariant)
            await interactor.execute(PRODUCT, form)
