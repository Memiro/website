from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

import structlog
from pydantic import BaseModel, Field

from memiro.application.common.gateway.catalog import AttributeGateway, ProductGateway
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.common.input_limits import MAX_SELECTIONS, MAX_SIDE_MM, MIN_SIDE_MM
from memiro.application.errors.catalog import AttributeValueNotFoundError, ProductNotFoundError
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, ProductId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.pricing.pricing_service import price_product, selection_deltas
from memiro.entities.pricing.quotation import PricingVerdict
from memiro_common.interactor import interactor
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)


class Selection(BaseModel):
    """One choice of the customer: what he put in place of the product's own value."""

    attribute_id: UUID
    value_id: UUID


class CalculatePriceForm(BaseModel):
    """The configuration the customer assembled in the product card."""

    product_id: UUID
    width_mm: int = Field(ge=MIN_SIDE_MM, le=MAX_SIDE_MM)
    height_mm: int = Field(ge=MIN_SIDE_MM, le=MAX_SIDE_MM)
    selections: list[Selection] = Field(default_factory=list[Selection], max_length=MAX_SELECTIONS)


class SelectionDelta(BaseModel):
    """What one choice of the customer cost, against the product's own default."""

    attribute_id: UUID
    value_id: UUID
    delta: Decimal


class CalculatedPrice(BaseModel):
    """The truncated projection of ``Quotation`` the storefront is allowed to see.

    The total, the deltas of the chosen add-ons and the machine verdict code —
    no tariffs, no factors and no lines of blade and edge (decision 56).
    """

    verdict: PricingVerdict
    total: Decimal
    selection_deltas: list[SelectionDelta]


@interactor
class CalculatePrice:
    """Interactor for pricing one configuration of a product."""

    product_gateway: ProductGateway
    attribute_gateway: AttributeGateway
    pricing_settings_gateway: PricingSettingsGateway

    async def execute(self, data: CalculatePriceForm) -> CalculatedPrice:
        """Price the configuration and answer with the projection the storefront may show."""
        logger.debug("Calculating a price", product_id=data.product_id)
        product_id = ProductId(data.product_id)
        product = await self.product_gateway.get(product_id)
        if product is None:
            logger.warning("Pricing asked for an unknown product", product_id=product_id)
            raise ProductNotFoundError
        settings = await self.pricing_settings_gateway.get()
        if settings is None:
            logger.warning("Pricing asked before the settings were created", product_id=product_id)
            raise PricingSettingsNotFoundError

        attributes = await self.attribute_gateway.list_with_values()
        selections = _selections(product, attributes, data.selections)
        dimensions = Dimensions(
            width=Millimeters(value=data.width_mm),
            height=Millimeters(value=data.height_mm),
        )
        quotation = price_product(
            product=product,
            attributes=attributes,
            settings=settings,
            dimensions=dimensions,
            selections=selections,
        )
        deltas = selection_deltas(
            product=product,
            attributes=attributes,
            settings=settings,
            dimensions=dimensions,
            selections=selections,
        )
        if quotation.total is None:
            msg = f"Verdict {quotation.verdict} left the price with no total"
            raise RuntimeError(msg)
        return CalculatedPrice(
            verdict=quotation.verdict,
            total=quotation.total.amount,
            selection_deltas=[
                SelectionDelta(
                    attribute_id=selection.attribute_id,
                    value_id=selection.value_id,
                    delta=deltas[AttributeId(selection.attribute_id)],
                )
                for selection in data.selections
            ],
        )


def _selections(
    product: Product,
    attributes: Sequence[Attribute],
    selections: Sequence[Selection],
) -> dict[AttributeId, AttributeValueId]:
    """Check every choice against the dictionary and the product, then index it by attribute.

    The customer *replaces* the product's own value, he does not introduce a
    setting the product never had: without something to replace, the add-on
    price would have nothing to be counted from (ADR-0007).
    """
    index = {attribute.id: attribute for attribute in attributes}
    chosen: dict[AttributeId, AttributeValueId] = {}
    for selection in selections:
        attribute_id = AttributeId(selection.attribute_id)
        value_id = AttributeValueId(selection.value_id)
        attribute = index.get(attribute_id)
        if attribute is None or attribute.value(value_id) is None or product.declared(attribute_id) is None:
            logger.warning(
                "A choice outside the product's dictionary",
                product_id=product.id,
                attribute_id=attribute_id,
                value_id=value_id,
            )
            raise AttributeValueNotFoundError
        chosen[attribute_id] = value_id
    return chosen
