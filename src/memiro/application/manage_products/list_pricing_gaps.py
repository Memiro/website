from collections.abc import Sequence

import structlog
from pydantic import BaseModel

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.identifiers import ProductId
from memiro.entities.pricing.pricing_service import pricing_gaps
from memiro_common.interactor import interactor
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)


def _gaps_of(product: Product, attributes: Sequence[Attribute]) -> "PricingGapsModel":
    """Say one product's gaps in names, the way the owner's screen shows them."""
    gaps = pricing_gaps(product, attributes)
    named = {attribute.id: attribute.name for attribute in attributes}
    return PricingGapsModel(
        undeclared_attributes=[named[attribute_id] for attribute_id in gaps.undeclared],
        nothing_is_paid=gaps.nothing_is_paid,
    )


class PricingGapsModel(BaseModel):
    """What one product still lacks before the calculator can price it."""

    undeclared_attributes: list[str]
    nothing_is_paid: bool


@interactor
class ListPricingGaps:
    """Interactor for telling why the products of one page carry no calculator."""

    product_gateway: ProductGateway
    attribute_gateway: AttributeGateway

    async def execute(self, product_ids: Sequence[ProductId]) -> dict[ProductId, PricingGapsModel]:
        """Say of every named product what its configuration is still missing.

        The answer is keyed by product and not paged: the caller names the
        products it is asking about, and one that is gone is simply absent.
        """
        logger.debug("Reading the pricing gaps of a page", count=len(product_ids))
        products = await self.product_gateway.list_by_ids(product_ids)
        attributes = await self.attribute_gateway.list_with_values()
        return {product.id: _gaps_of(product, attributes) for product in products}
