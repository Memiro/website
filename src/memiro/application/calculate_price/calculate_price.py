from decimal import Decimal
from uuid import UUID

import structlog
from pydantic import BaseModel, Field, model_validator

from memiro.application.common.customer_selection import Selection, customer_selections
from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.input_limits import MAX_SELECTIONS, MAX_SIDE_MM, MIN_SIDE_MM
from memiro.application.errors.catalog import ProductNotFoundError
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.entities.common.identifiers import ProductId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.pricing.pricing_service import price_product_for_customer, selection_deltas
from memiro.entities.pricing.quotation import PricingVerdict
from memiro_common.interactor import interactor
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)


class CalculatePriceForm(BaseModel):
    """The configuration the customer assembled in the product card."""

    product_id: UUID
    width_mm: int = Field(ge=MIN_SIDE_MM, le=MAX_SIDE_MM)
    height_mm: int = Field(ge=MIN_SIDE_MM, le=MAX_SIDE_MM)
    selections: list[Selection] = Field(default_factory=list[Selection], max_length=MAX_SELECTIONS)

    @model_validator(mode="after")
    def _one_choice_per_attribute(self) -> "CalculatePriceForm":
        """Refuse two choices on one attribute: the second would be priced and the first still answered."""
        attribute_ids = [selection.attribute_id for selection in self.selections]
        if len(set(attribute_ids)) != len(attribute_ids):
            msg = "An attribute can be chosen only once"
            raise ValueError(msg)
        return self


class SelectionDelta(BaseModel):
    """What one choice of the customer cost, against the product's own default."""

    attribute_id: UUID
    value_id: UUID | None
    delta: Decimal


class CalculatedPrice(BaseModel):
    """The truncated projection of ``Quotation`` the storefront is allowed to see.

    The total, the deltas, the applied size threshold and the machine verdict
    code — no tariffs, no factors and no lines of blade and edge (decision 56).
    """

    verdict: PricingVerdict
    total: Decimal | None
    selection_deltas: list[SelectionDelta]
    size_surcharge_from_long_side_mm: int | None = None


@interactor
class CalculatePrice:
    """Interactor for pricing one configuration of a product."""

    product_gateway: ProductGateway
    pricing_settings_gateway: PricingSettingsGateway
    attribute_gateway: AttributeGateway

    async def execute(self, data: CalculatePriceForm) -> CalculatedPrice:
        """Price the configuration and answer with the projection the storefront may show."""
        logger.debug("Calculating a price", product_id=data.product_id)
        product_id: ProductId = data.product_id
        product = await self.product_gateway.get(product_id)
        if product is None:
            logger.warning("Pricing asked for an unknown product", product_id=product_id)
            raise ProductNotFoundError
        settings = await self.pricing_settings_gateway.get_with_surcharges()
        if settings is None:
            logger.warning("Pricing asked before the settings were created", product_id=product_id)
            raise PricingSettingsNotFoundError

        attributes = await self.attribute_gateway.list_with_values()
        selections = customer_selections(product, attributes, data.selections)
        dimensions = Dimensions(
            width=Millimeters(value=data.width_mm),
            height=Millimeters(value=data.height_mm),
        )
        quotation = price_product_for_customer(
            product=product,
            attributes=attributes,
            settings=settings,
            dimensions=dimensions,
            selections=selections,
        )
        size_surcharge_from_long_side_mm = (
            quotation.size_surcharge_from_long_side_mm.value
            if quotation.size_surcharge_from_long_side_mm is not None
            else None
        )
        if quotation.verdict is not PricingVerdict.PRICED:
            return CalculatedPrice(
                verdict=quotation.verdict,
                total=None,
                selection_deltas=[],
                size_surcharge_from_long_side_mm=size_surcharge_from_long_side_mm,
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
                    delta=deltas[selection.attribute_id],
                )
                for selection in data.selections
                if selection.attribute_id in deltas
            ],
            size_surcharge_from_long_side_mm=size_surcharge_from_long_side_mm,
        )
