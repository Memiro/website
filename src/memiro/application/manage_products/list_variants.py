from collections.abc import Sequence
from decimal import Decimal

import structlog
from pydantic import BaseModel

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.manage_products.shared import loaded_for_reading
from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.catalog.product.entity import DeclaredValue, Product, Variant
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, ProductId, VariantId
from memiro_common.interactor import interactor
from memiro_common.logger import Logger

# What an override names when the dictionary row behind it is gone: the panel
# still shows the variant, and a name it cannot read is not a reason to hide it.
UNNAMED = "—"

logger: Logger = structlog.get_logger(__name__)


class VariantOverrideModel(BaseModel):
    """One difference between a variant and the product, named the way the owner reads it."""

    attribute_id: AttributeId
    attribute_name: str
    value_id: AttributeValueId | None
    value_name: str | None
    quantity: Decimal | None


class VariantModel(BaseModel):
    """One precalculated variant as the owner's panel shows it."""

    id: VariantId
    width_mm: int
    height_mm: int
    price: Decimal
    sort_order: int
    overrides: list[VariantOverrideModel]
    sets_product_price: bool


class VariantsList(BaseModel):
    """The whole panel of one product, in the order the owner gave it."""

    items: list[VariantModel]
    total: int


def _named(
    override: DeclaredValue,
    attributes: dict[AttributeId, Attribute],
) -> VariantOverrideModel:
    """Say one override in the words of its attribute and its dictionary row."""
    attribute = attributes.get(override.attribute_id)
    row = attribute.value(override.chosen.value_id) if attribute and override.chosen.value_id else None
    return VariantOverrideModel(
        attribute_id=override.attribute_id,
        attribute_name=attribute.name if attribute else UNNAMED,
        value_id=override.chosen.value_id,
        value_name=row.name if row else None,
        quantity=override.chosen.quantity,
    )


def _listed(variant: Variant, product: Product, attributes: dict[AttributeId, Attribute]) -> VariantModel:
    """Show one variant with the mark the storefront price puts on the cheapest of them."""
    return VariantModel(
        id=variant.id,
        width_mm=variant.dimensions.width.value,
        height_mm=variant.dimensions.height.value,
        price=variant.price.amount,
        sort_order=variant.sort_order,
        overrides=[_named(override, attributes) for override in variant.overrides],
        sets_product_price=variant.price == product.price_from,
    )


@interactor
class ListVariants:
    """Interactor for showing the owner the variants his panel redraws."""

    product_gateway: ProductGateway
    attribute_gateway: AttributeGateway

    async def execute(self, product_id: ProductId) -> VariantsList:
        """List the variants of one product in the owner's order, differences named in words."""
        logger.debug("Reading the variants of a product", product_id=product_id)
        product = await loaded_for_reading(
            self.product_gateway, product_id, command="list_variants", with_variants=True
        )
        attributes: Sequence[Attribute] = await self.attribute_gateway.list_with_values()
        named = {attribute.id: attribute for attribute in attributes}
        listed = [_listed(variant, product, named) for variant in product.variants]
        return VariantsList(items=listed, total=len(listed))
