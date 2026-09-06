"""What the repricing tests arrange: priced variants, and the reading taken after the handler."""

from dishka import AsyncContainer

from memiro.application.common.gateway.product import ProductGateway
from memiro.application.manage_products import AddVariant, AddVariantForm
from memiro.application.reprice_products import RepriceProducts
from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.identifiers import VariantId
from memiro.entities.common.money import Money
from tests.common.factory.catalog import PRODUCT


async def arranged_variant(
    container: AsyncContainer,
    *,
    width_mm: int,
    height_mm: int,
    sort_order: int = 0,
) -> VariantId:
    """Put one precalculated variant on the canonical product through its own command."""
    async with container() as request:
        interactor = await request.get(AddVariant)
        created = await interactor.execute(
            PRODUCT,
            AddVariantForm(width_mm=width_mm, height_mm=height_mm, overrides=[], sort_order=sort_order),
        )
    return created.id


async def reprice(container: AsyncContainer) -> int:
    """Run the repricing handler in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(RepriceProducts)
        return await interactor.execute()


async def load_product(container: AsyncContainer) -> Product:
    """Read the canonical product with its children back in a fresh transaction."""
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        product = await gateway.get(PRODUCT, eager_variants=True)
    assert product is not None
    return product


async def prices_after(container: AsyncContainer) -> tuple[Money, ...]:
    """Read the prices of the canonical product's variants, in the owner's order."""
    product = await load_product(container)
    return tuple(variant.price for variant in product.variants)
