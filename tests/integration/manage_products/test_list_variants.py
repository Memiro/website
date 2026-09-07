from uuid import uuid4

import pytest
from dishka import AsyncContainer

from memiro.application.errors.catalog import ProductNotFoundError
from memiro.application.manage_products import (
    AddVariant,
    AddVariantForm,
    ListVariants,
    VariantOverrideModel,
)
from memiro.application.manage_products.shared import VariantOverrideForm
from tests.common.factory.catalog import BLADE, GRAPHITE, PRODUCT

pytestmark = pytest.mark.usefixtures("catalog")

BLADE_NAME = "Тип полотна"
GRAPHITE_NAME = "Графит"


async def _add(container: AsyncContainer, form: AddVariantForm) -> None:
    """Put one variant on the demo product through its own command."""
    async with container() as request:
        interactor = await request.get(AddVariant)
        await interactor.execute(PRODUCT, form)


async def test_the_panel_reads_the_variants_in_the_order_the_owner_gave_them(
    container: AsyncContainer,
) -> None:
    """The list the panel redraws is ordered by the owner, not by the moment of writing."""
    await _add(container, AddVariantForm(width_mm=900, height_mm=700, overrides=[], sort_order=5))
    await _add(container, AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=1))

    async with container() as request:
        interactor = await request.get(ListVariants)
        listed = await interactor.execute(PRODUCT)

    assert [(variant.width_mm, variant.sort_order) for variant in listed.items] == [(800, 1), (900, 5)]


async def test_the_cheapest_variant_is_the_one_the_storefront_price_comes_from(
    container: AsyncContainer,
) -> None:
    """The mark the panel shows follows ``price_from``: the storefront quotes the cheapest variant."""
    await _add(container, AddVariantForm(width_mm=800, height_mm=600, overrides=[], sort_order=0))
    await _add(container, AddVariantForm(width_mm=1200, height_mm=900, overrides=[], sort_order=1))

    async with container() as request:
        interactor = await request.get(ListVariants)
        listed = await interactor.execute(PRODUCT)

    assert [variant.sets_product_price for variant in listed.items] == [True, False]


async def test_a_variant_names_in_words_what_it_changes_about_the_product(
    container: AsyncContainer,
) -> None:
    """The owner reads the differences of a variant, not the identifiers behind them."""
    await _add(
        container,
        AddVariantForm(
            width_mm=800,
            height_mm=600,
            overrides=[VariantOverrideForm(attribute_id=BLADE, value_id=GRAPHITE)],
            sort_order=0,
        ),
    )

    async with container() as request:
        interactor = await request.get(ListVariants)
        listed = await interactor.execute(PRODUCT)

    assert listed.items[0].overrides == [
        VariantOverrideModel(
            attribute_id=BLADE,
            attribute_name=BLADE_NAME,
            value_id=GRAPHITE,
            value_name=GRAPHITE_NAME,
            quantity=None,
        ),
    ]


async def test_a_product_without_variants_is_listed_as_an_empty_panel(
    request_container: AsyncContainer,
) -> None:
    """A product nobody has built variants for answers with an empty list, not a refusal."""
    interactor = await request_container.get(ListVariants)

    listed = await interactor.execute(PRODUCT)

    assert listed.items == []


async def test_listing_fails_if_the_product_is_unknown(request_container: AsyncContainer) -> None:
    """A list for an identifier nobody issued is rejected with PRODUCT_NOT_FOUND."""
    interactor = await request_container.get(ListVariants)

    with pytest.raises(ProductNotFoundError):
        await interactor.execute(uuid4())
