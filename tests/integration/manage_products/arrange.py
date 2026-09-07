"""Forms and readings the four product scenarios share."""

from dishka import AsyncContainer

from memiro.application.common.gateway.product import ProductGateway
from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.identifiers import AttributeId, ProductId


async def load_product(container: AsyncContainer, product_id: ProductId) -> Product | None:
    """Read the whole product back in a fresh transaction after a command."""
    async with container() as request:
        gateway: ProductGateway = await request.get(ProductGateway)
        return await gateway.get(product_id, eager_images=True)


def declared_index(product: Product) -> dict[AttributeId, ChosenValue]:
    """Read what the product declares as one entry per attribute: a declaration is not hashable."""
    return {declared.attribute_id: declared.chosen for declared in product.declared_values}
